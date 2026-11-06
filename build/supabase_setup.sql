-- ===== 备考刷题 云端安全升级 v2 =====
-- 1) 失败锁定表：同一名字错 5 次锁 10 分钟（防 6 位 PIN 在线爆破）
create table if not exists auth_fail(
  name text primary key,
  fails int not null default 0,
  lock_until timestamptz
);

create or replace function bk_lock_check(p_name text) returns void
language plpgsql security definer set search_path=public as $$
declare v_until timestamptz;
begin
  select lock_until into v_until from auth_fail where name=p_name;
  if v_until is not null and v_until > now() then
    raise exception '尝试次数过多，% 前请勿再试', to_char(v_until,'HH24:MI');
  end if;
end $$;

create or replace function bk_fail(p_name text) returns void
language plpgsql security definer set search_path=public as $$
begin
  insert into auth_fail(name,fails,lock_until) values(p_name,1,null)
    on conflict(name) do update set fails=auth_fail.fails+1,
      lock_until=case when auth_fail.fails+1>=5 then now()+interval '10 minutes' else null end;
end $$;

create or replace function bk_pass_ok(p_name text) returns void
language sql security definer set search_path=public as $$
  delete from auth_fail where name=p_name;
$$;

-- 2) 读进度：锁定检查 + 密码哈希二次哈希比对（防 pass-the-hash）+ 成功清失败计数
create or replace function bk_load(p_name text, p_salt text, p_hash text)
returns table (state jsonb, updated_at timestamptz)
language plpgsql security definer set search_path=public as $$
declare v_row progress; v_h text;
begin
  if p_name is null or length(trim(p_name))=0 or length(trim(p_name))>20
     or p_hash is null or length(p_hash)<>64 then
    return;
  end if;
  perform bk_lock_check(trim(p_name));
  v_h := encode(sha256(convert_to(p_hash,'UTF8')),'hex');
  select * into v_row from progress pr where pr.name = trim(p_name);
  if not found then
    return;  -- 新名字，无云端数据
  end if;
  if v_row.pwd_hash <> v_h then
    perform bk_fail(trim(p_name));
    raise exception '密码不正确';
  end if;
  perform bk_pass_ok(trim(p_name));
  return query select v_row.state, v_row.updated_at;
end $$;

-- 3) 保存：新名建号（含总数上限）；已有名字错密码拒绝并计失败；输入限长/限量
create or replace function bk_save(p_name text, p_salt text, p_hash text, p_state jsonb)
returns text
language plpgsql security definer set search_path=public as $$
declare v_row progress; v_h text;
begin
  if p_name is null or length(trim(p_name))=0 or length(trim(p_name))>20
     or p_hash is null or length(p_hash)<>64 or p_state is null
     or octet_length(p_state::text)>262144 then
    return 'error';
  end if;
  perform bk_lock_check(trim(p_name));
  v_h := encode(sha256(convert_to(p_hash,'UTF8')),'hex');
  select * into v_row from progress pr where pr.name = trim(p_name);
  if not found then
    if (select count(*) from progress) >= 500 then
      raise exception '云同步名额已满（500），请联系管理员清理';
    end if;
    insert into progress(name, pwd_salt, pwd_hash, state)
      values (trim(p_name), coalesce(p_salt,''), v_h, p_state);
    perform bk_pass_ok(trim(p_name));
    return 'created';
  end if;
  if v_row.pwd_hash <> v_h then
    perform bk_fail(trim(p_name));
    raise exception '密码不正确';
  end if;
  update progress set state = p_state, pwd_salt = coalesce(p_salt,''), updated_at = now()
    where name = trim(p_name) and pwd_hash = v_h;
  perform bk_pass_ok(trim(p_name));
  return 'ok';
end $$;

-- 4) 改密码：验证旧密码（失败也计锁定）后更换
create or replace function bk_chpwd(p_name text, p_old_hash text, p_new_salt text, p_new_hash text)
returns text
language plpgsql security definer set search_path=public as $$
declare v_h_old text; v_h_new text;
begin
  if length(coalesce(p_old_hash,''))<>64 or length(coalesce(p_new_hash,''))<>64 then
    return 'error';
  end if;
  perform bk_lock_check(trim(p_name));
  v_h_old := encode(sha256(convert_to(p_old_hash,'UTF8')),'hex');
  v_h_new := encode(sha256(convert_to(p_new_hash,'UTF8')),'hex');
  if not exists(select 1 from progress where name = trim(p_name) and pwd_hash = v_h_old) then
    perform bk_fail(trim(p_name));
    raise exception '旧密码不正确';
  end if;
  update progress set pwd_salt = coalesce(p_new_salt,''), pwd_hash = v_h_new
    where name = trim(p_name) and pwd_hash = v_h_old;
  perform bk_pass_ok(trim(p_name));
  return 'ok';
end $$;

grant execute on function bk_load(text, text, text) to anon;
grant execute on function bk_save(text, text, text, jsonb) to anon;
grant execute on function bk_chpwd(text, text, text, text) to anon;

-- ===== bk_load v3：错密码返回 state=null 哨兵行（失败计数可持久化，不被回滚） =====
create or replace function bk_load(p_name text, p_salt text, p_hash text)
returns table (state jsonb, updated_at timestamptz)
language plpgsql security definer set search_path=public as $$
declare v_row progress; v_h text;
begin
  if p_name is null or length(trim(p_name))=0 or length(trim(p_name))>20
     or p_hash is null or length(p_hash)<>64 then
    return;
  end if;
  perform bk_lock_check(trim(p_name));
  v_h := encode(sha256(convert_to(p_hash,'UTF8')),'hex');
  select * into v_row from progress pr where pr.name = trim(p_name);
  if not found then
    return;  -- 新名字，无云端数据
  end if;
  if v_row.pwd_hash <> v_h then
    perform bk_fail(trim(p_name));   -- 计失败（无 raise，可持久化）
    return query select null::jsonb, null::timestamptz;  -- 哨兵：存在但密码错
    return;  -- 必须立即退出，否则继续执行会把真实进度也返回（安全漏洞）
  end if;
  perform bk_pass_ok(trim(p_name));
  return query select v_row.state, v_row.updated_at;
end $$;

-- ===== bk_save v3：错密码返回 wrong_password（不再 raise，失败计数可持久化） =====
create or replace function bk_save(p_name text, p_salt text, p_hash text, p_state jsonb)
returns text
language plpgsql security definer set search_path=public as $$
declare v_row progress; v_h text;
begin
  if p_name is null or length(trim(p_name))=0 or length(trim(p_name))>20
     or p_hash is null or length(p_hash)<>64 or p_state is null
     or octet_length(p_state::text)>262144 then
    return 'error';
  end if;
  perform bk_lock_check(trim(p_name));
  v_h := encode(sha256(convert_to(p_hash,'UTF8')),'hex');
  select * into v_row from progress pr where pr.name = trim(p_name);
  if not found then
    if (select count(*) from progress) >= 500 then
      raise exception '云同步名额已满（500），请联系管理员清理';
    end if;
    insert into progress(name, pwd_salt, pwd_hash, state)
      values (trim(p_name), coalesce(p_salt,''), v_h, p_state);
    perform bk_pass_ok(trim(p_name));
    return 'created';
  end if;
  if v_row.pwd_hash <> v_h then
    perform bk_fail(trim(p_name));
    return 'wrong_password';
  end if;
  update progress set state = p_state, pwd_salt = coalesce(p_salt,''), updated_at = now()
    where name = trim(p_name) and pwd_hash = v_h;
  perform bk_pass_ok(trim(p_name));
  return 'ok';
end $$;

-- ===== bk_chpwd v3：错旧密码返回 wrong_password =====
create or replace function bk_chpwd(p_name text, p_old_hash text, p_new_salt text, p_new_hash text)
returns text
language plpgsql security definer set search_path=public as $$
declare v_h_old text; v_h_new text;
begin
  if length(coalesce(p_old_hash,''))<>64 or length(coalesce(p_new_hash,''))<>64 then
    return 'error';
  end if;
  perform bk_lock_check(trim(p_name));
  v_h_old := encode(sha256(convert_to(p_old_hash,'UTF8')),'hex');
  v_h_new := encode(sha256(convert_to(p_new_hash,'UTF8')),'hex');
  if not exists(select 1 from progress where name = trim(p_name) and pwd_hash = v_h_old) then
    perform bk_fail(trim(p_name));
    return 'wrong_password';
  end if;
  update progress set pwd_salt = coalesce(p_new_salt,''), pwd_hash = v_h_new
    where name = trim(p_name) and pwd_hash = v_h_old;
  perform bk_pass_ok(trim(p_name));
  return 'ok';
end $$;
