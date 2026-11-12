# ezlogin 笔记（未解出，待题解）

目标：`http://4640351189e00439709f099a.http-ctf2.dasctf.com:80`（dasctf，per-player 实例，可能已过期）。

## 题目结构（已确认）

- `/` 登录页：`username` + `password`，POST 提交。
  - 非 localhost POST 返回「只有本地管理员才能登陆！」（`$_SERVER['REMOTE_ADDR']` 检查）。
- `/robots.txt` → `Disallow: y0u_nev3r_gue5s_1t.php`。
- `/y0u_nev3r_gue5s_1t.php` 是 SSRF，源码（highlight_file 直接可见）：

```php
$url = $_POST['url'];
if(preg_match("/file|dict/i", $url)) die("?????");
if($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_HEADER, 0);
    curl_exec($ch);   // 直接 echo 响应
    curl_close($ch);
}
```

过滤只拦 `file` 和 `dict` 子串，`gopher://` 可用。

## 关键坑：gopher 载荷要预编码（通用，可复用）

SSRF 的 PHP 会先对 `$_POST['url']` 做一次 URL 解码，再把结果交给 curl。所以 gopher 载荷里的
空格/CRLF **必须预编码**（`%20`/`%0d%0a`，`&`→`%26`），否则：

- 直接发原始空格/CRLF → PHP 解码成原始字节 → curl 无法解析 URL → `curl_exec` 返回空；
- 裸 `&` → PHP 把它当 POST 参数分隔符，`url` 值被截断。

正确做法（用 `httpx.post(data={'url': gopher})` 会自动把 `%` 再编码成 `%25`，正好是需要的双重编码）：

```python
import httpx
from urllib.parse import quote
inner = (f"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\n"
         f"Content-Type: application/x-www-form-urlencoded\r\n"
         f"Content-Length: {len(body)}\r\n\r\n{body}")
gopher = "gopher://127.0.0.1:80/_" + quote(inner, safe="")
r = httpx.post(".../y0u_nev3r_gue5s_1t.php", data={"url": gopher})
```

这样 `curl` 会收到仍带 `%20`/`%0d%0a` 的 URL，解码后发原始 HTTP 请求。已验证能拿到内网 Apache 的原始响应。

## 已通过的部分

- gopher GET/POST 到 `127.0.0.1:80` 都能拿到内网 Apache 响应。
- gopher POST 到 `/`（登录）能通过「只有本地管理员才能登陆」的 localhost 检查。

## 卡点：登录页 WAF

从 localhost POST 登录时，登录页还有一个 WAF，命中返回 `?????`。已探明的拦截字符：

- 拦截：`'`（单引号）、`"`（双引号）、空白符（`\s`）、`=`、`union`（子串，大小写不敏感）。
- **不拦**：`\`（反斜杠）、`#`、`--`、`/*` `*/`、`(` `)`、`select`、`or`、`and`、`from`、`where`。

推测登录 SQL：`SELECT * FROM users WHERE username='$u' AND password='$p'`，且很可能还做了
`addslashes`（反斜杠逃逸 `admin\` + `or/**/1#` 试过无效，返回普通表单）。常见弱口令（admin/admin、
123456、password、root 等 ~30 个）都不对。

## 其它发现

- `php://filter`、`data://` 经 curl 无效（libcurl 不认 PHP 流包装器），返回空。
- `file://` 被 `file` 过滤拦住；null 字节 `fi%00le` 让 curl 报错，也没读到文件。
- 备份文件 `index.php.bak`/`index.php~`/`index.phps` 等 404。
- 内网 `127.0.0.1:3306` 有 **MySQL 5.7.29**（gopher 握手可见），大概率是登录的库。

## 待题解后补的下一步

1. 登录 SQLi 的 WAF 绕过（空格→`/**/`、`=`→`LIKE`/`>`、`'`/`"` 的绕过——反斜杠若被 addslashes 吃掉，
   需换思路，例如确认是否真 addslashes、或走 GBK/双编码）。
2. 或：用 Gopherus 之类工具生成 gopher 载荷直接读 `127.0.0.1:3306` 的 MySQL，把 flag/密码捞出来。
3. flag 前缀：`flag`（custom 会话里填的默认值，未验证）。
