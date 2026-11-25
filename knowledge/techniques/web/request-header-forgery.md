# 请求头伪造：过 Referer / User-Agent / 来源 IP 校验

**一句话**：页面报「必须从某站点访问 / 必须用某浏览器 / 只能本地访问」时，按报错文案逐层伪造
Referer、User-Agent、以及来源 IP 头（`X-Forwarded-For` 等）。IP 头有多个变体，前置代理可能覆盖其中
某几个，要**逐个试**，别一上来就下「必须 SSRF / 校验 REMOTE_ADDR」的结论。

## 触发信号

- 直接访问某页面返回类似 `It doesn't come from 'https://xxx'`、`must be accessed locally`、
  `use xxx browser`、`只能本地访问`。
- 首页源码里有隐藏链接指向某个 `.php`（如 `Secret.php`）。

## 套路

按报错文案逐层加头，每过一层报错会变，据此定位缺哪个：

1. **Referer**：报错点名站点 → 设 `Referer: <报错里的完整域名>`（**带全 `https://` 协议 + 完整域名**，别只写裸域名）。
2. **User-Agent**：报错要某浏览器 → 设 `User-Agent: <报错里的词>`（如 `Syclover`）。
3. **来源 IP**（报「本地 / local」）→ 伪造 IP 头为 `127.0.0.1`，按优先级逐个试：
   - `X-Forwarded-For`
   - `X-Real-IP`
   - `Client-IP`、`X-Client-IP`
   - `X-Originating-IP`
   - `X-Remote-IP`、`X-Remote-Addr`
   - `Forwarded`、`X-Forwarded`
4. **Origin**：部分题还会校验 `Origin`，可一并设为与 Referer 相同的域名。

## 坑

- **前置代理（nginx/CDN）常覆盖 `X-Forwarded-For`**，把它改成真实客户端 IP。所以某个 IP 头试了
  没效果时，**换下一个变体**，不要卡死或跳到「必须 SSRF」——绝大多数「本地访问」题靠伪造 IP 头就能解。
- 可以一次性把多个 IP 头都设成 `127.0.0.1` 一起发；若仍被拒，再单独逐个试那些少见头。
- 一层校验一个响应，务必读完整个 body 的报错变化，再决定加哪个头。
