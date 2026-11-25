# SQL 注入过滤绕过：/**/ 顶空格、替代表、无列名注入

**一句话**：WAF 把空格、`or`/`and`、`information_schema` 等过滤后，用 `/**/` 当空格、`&&`/`||`
当 and/or、`mysql.innodb_table_stats` 当 information_schema，最后用「无列名注入」读列数据。

## 触发信号

- 详情/查询接口的 id 参数单引号闭合后有报错/回显差异。
- fuzz 发现空格、`or`、`and`、`information_schema` 等关键词被过滤。

## 套路

1. **空格** → `/**/`（也可试 `%09` tab、`%0a` 换行、括号 `(1)`）。
2. **and / or** → `&&` / `||`（URL 里编码成 `%26%26` / `%7c%7c`）。
3. **information_schema** → `mysql.innodb_table_stats`（有 `database_name`、`table_name` 两列），
   或 `sys.schema_table_statistics`。
4. **猜列数 / 回显位**：`order/**/by N` 或 `group/**/by N` 二分。
5. **无列名注入**（union 列数已知、但拿不到列名）：把未知列名映射成别名再选，如
   `select \`2\` from (select 1,2,3 union select * from users) a` —— 内层把 users 的列重命名成
   1/2/3，外层按 `\`2\`` 取第 2 列。

## 坑

- `mysql.innodb_table_stats` 的 `database_name` 是库名、`table_name` 是表名；先拿表名，再无列名读列。
- union 的列数必须和原查询列数一致，否则报错。
- 逐层确认报错变化再推进，别一次塞太多绕过。
