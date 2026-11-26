# XXE：外部实体读文件与常见变形

**一句话**：服务端把请求体当 XML 解析且允许外部实体时，用 DOCTYPE 声明
`<!ENTITY x SYSTEM "file:///flag.txt">` 并在正文里引用 `&x;`，让解析器把目标文件内容
回显到响应里。

## 触发信号

关键词：XXE / XML external entity / file read / SSRF / blind XXE。
- 请求体是 XML、SOAP、SVG、DOCX/XLSX 上传，或 `Content-Type: application/xml`。
- 回显字段里出现你提交的某个 XML 节点内容（说明服务端解析后回显）。
- 报错带 XML parser 字样，或对格式错误的 XML 返回解析错误。

## 套路

1. **最简读文件**：
   ```xml
   <?xml version="1.0"?>
   <!DOCTYPE r [<!ENTITY x SYSTEM "file:///flag.txt">]>
   <r><name>&x;</name></r>
   ```
   把实体放进会被回显的节点；不同题可能回显 name/message/comment 等。
2. **绝对路径**优先 `/flag.txt`、`/flag`、`/etc/passwd`；相对路径看服务端 cwd。
3. **读源码/绕过编码**：PHP 环境用
   `php://filter/convert.base64-encode/resource=index.php`，拿到 base64 再解码。
4. **报错外带（blind XXE）**：不能回显时，用参数实体 + 外部 DTD 把内容塞进错误信息，
   或直接 SSRF 到内网/元数据地址（`http://169.254.169.254/...`）。
5. **过滤绕过**：UTF-16/UTF-7 编码声明、`SYSTEM` 大小写/实体拼接、把 DOCTYPE 放在
   注释外合法位置；确认解析器是否禁用了外部实体（禁用则换 SSRF/其他入口）。
6. **SVG/DOCX**：上传场景把同样 DOCTYPE 塞进 SVG 或 XML part，服务端渲染/解压时触发。

## 坑

- 实体必须被**引用**才会展开；只声明不引用等于没发。
- 有的解析器只展开第一个 DOCTYPE 里声明的实体；参数实体在内部子集里的用法受限。
- 回显节点猜错会看起来"没效果"：先用普通 XML 确认哪个字段被回显，再把实体放进去。
- `&` 在 URL/表单里要编码；JSON 包装的 XML 注意转义。
- 失败先确认外部实体是否被禁用，再考虑 blind/OOB 变体，别反复改实体名。
