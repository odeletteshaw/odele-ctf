# PHP 反序列化：字符串逃逸（filter 改变长度后注入字段）

**一句话**：应用对用户可控值先 `serialize`、再 `preg_replace`/`str_replace` 过滤、然后存库或
`unserialize` 时，过滤把某个子串换成不同长度的串，导致 `s:N:` 声明长度与过滤后的实际内容不一致。
用 `str_repeat(触发词, strlen(注入串))` 填充，把注入串「顶」出字符串边界，变成新的序列化字段。

## 触发信号

- 源码里：`serialize($_POST['x'])` → `filter()`（`preg_replace`/`str_replace`）→ 存库 → 之后
  `unserialize`。
- 过滤把某子串替换成**不同长度**（如 `where`(5) → `hacker`(6)，+1；或反过来 -1）。
- 题面提到 profile / session / 序列化 / 字符串逃逸 / 键值逃逸。

## 核心套路（长度变长型，+d 字节）

```php
$payload = '";}s:5:"photo";s:10:"config.php";}';   // 想注入的新字段（photo=config.php）
$input   = str_repeat('where', strlen($payload)) . $payload;
```

原理（触发词 5→6，即每处 +1）：

- serialize 得 `s:N:"` + `where×len(payload)` + payload + `"`，其中 N = 5·len + len。
- 过滤后 `where×len` 变成 `hacker×len`，前 6·len 字节正好等于 N，于是第 N+1 字节（payload 开头的
  `"`）成了字符串的闭合引号；payload 剩下的 `;}s:5:"photo";…;}` 被解析成新字段。
- 结果：在反序列化对象里塞进 `photo=config.php` 之类的字段，绕过原始赋值逻辑。

## 长度变短型（-d 字节）

若过滤是长→短（如 `hacker`(6) → `where`(5)），`s:N:` 比实际内容长，解析器会把后面的字段「吃」进
字符串里。这时方向相反：先写一个正常字段，再用触发词把缺口补齐，让后续恶意字段正好落在解析边界上。

## 坑

- `str_repeat` 的次数必须**恰好等于 `strlen(payload)`**；多一次少一次边界对不齐，`unserialize` 直接报错。
- 触发词必须是**源码里确实会被替换的那个词**，替换前后长度差决定是「顶出」还是「吃进」。
- 注入串里的 `"` 不需要转义——serialize 靠 `s:N:` 长度定位内容，不转义引号；别手动加 `\"`。

## 关联

- 同属 PHP 反序列化：private `\0` 空字节、`__wakeup`/CVE-2016-7124（见 web 的 system prompt）。
- 先 `download_file` 拿 www.zip 源码，再找 `serialize`/`filter`/`unserialize` 三件套。
