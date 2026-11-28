---
id: set-cookie-leaks-auth-field-flip-boolean
name: Set-Cookie 泄露权限字段名：直接改写布尔 cookie 越权
description: 登录/校验接口用 Set-Cookie 下发权限标志（如 admin=0）时，字段名与取值形态即攻击面：直接改值试 1/true/yes 等布尔真值即可越权，无需签名破解。
tags: [web, harvested]
source: harvested
imported_at: 2026-11-27
---

# Set-Cookie 泄露权限字段名：直接改写布尔 cookie 越权

## 触发信号
- 首页极简（只有标题 + 一个按钮/链接），文案如「Plz login」「只有 admin 才可以获取 flag」。
- 点击登录/校验链接后，响应 body 为空但带 `Set-Cookie: <权限字段>=0; Path=/; Domain=...; Max-Age=...`——服务端主动把「权限状态」写进客户端 cookie。
- 该 cookie 无签名、无 HMAC、无 JWT 结构（不是 `xxx.yyy.zzz`），只是裸值。

## 步骤
1. 先无 cookie 请求登录/校验端点，**完整读响应头**（`Set-Cookie` 常是唯一线索，body 可能是空的）。
2. 从 cookie 名推断权限语义（`admin`、`role`、`is_admin`、`vip`、`level`、`auth`），从值推断类型（`0`/`1` 布尔、`guest`/`admin` 枚举、数字等级）。
3. 用同一端点回放，把该 cookie 改成「真值」候选，一次批量试：`1`、`true`、`True`、`yes`、`on`、`admin`、`2`、`999`、`-1`。**不同后端比较方式不同**：PHP 松散比较 `"1"==1` 真、`"true"==1` 假；Go/严格比较只认 `"1"`；有的用 `!= "0"` 则任何非 0 值都过。
4. 命中后立刻在同一响应里找 flag；若该端点只回显状态，再带着这个 cookie 去 `/flag`、`/admin`、`/getflag` 等兄弟路由。
5. 若 cookie 值看起来是 base64/hex 且长度固定，才转去考虑签名伪造（JWT alg=none、弱密钥爆破、CBC 位翻转），不要一上来就假设加密。

## 证据/验证
- 无 cookie 请求 `/check` → 200、`content-length: 0`、`Set-Cookie: admin=0; Path=/; Domain=127.0.0.1; Max-Age=3600`。
- 带 `Cookie: admin=1` 请求同一端点 → 200，body 直接返回 flag。
- 带 `Cookie: admin=true` → 200 空 body，证明后端是严格字符串/数值比较，只有 `1` 通过。

## 坑
- **空 body 不等于没线索**：本例 flag 端点无 cookie 时 body 为空，唯一信息在 `Set-Cookie` 头里；只看 body 会误判「端点无效」而转去 fuzz 目录。
- **`Domain=127.0.0.1` 是干扰项**：它只影响浏览器是否回传 cookie，用工具手动发 `Cookie:` 头时完全不受限，不要因此去构造 SSRF 或改 Host。实测带 `Host: 127.0.0.1` 反而落到 Nginx 默认虚拟主机返回 404。
- **布尔真值不是通用的**：`true`/`yes` 常失败，先试 `1`；反之若后端是 `!= "0"` 逻辑，`true` 也能过——所以批量试一组而不是只试一个。
- **别在无参数站点上堆注入载荷**：页面无任何输入参数时，SQLi/SSTI/反序列化都无从谈起，优先做「客户端可控状态」类检查（cookie、隐藏字段、localStorage 语义）。
- 两个入口（http:80 与 https:9999）返回同一份 HTML 时是同一应用，不必当成两个独立目标重复侦察。
