GENERATE_CYPHER_PROMPT = """

#  核心目标
基于检索到的实体关系，快速生成准确、高效的 Cypher 查询。优先使用模板匹配，提高响应速度。

# 输入数据
- 用户问题: {user_question}
- 实体关系数据: {entities_relations}

## 数据结构说明
entities 字段：
- name：实体名
- label：实体类型  
- entity_description：实体描述
- 其他属性名称：其他属性值

relations 字段：
- head：关系头实体名
- relation_type：关系类型
- tail：关系尾实体名
- relation_description：关系描述



# 任务要求：
1. 理解用户问题，如果涉及多个问题，则先拆分成子问题。
2. 基于提供的实体关系数据，生成可在 Neo4j 直接运行的 Cypher 查询，注意生成Cypher要遵循以下规则：
  - 实体：仅取自 entities.name, relations.head, relations.tail
  - 关系：仅取自 relations，并保持原有head-relation_type-tail之前的对应关系
  - 标签：仅取自 label
  - 属性应为entities对象的字段，关系应为relations列表中的对象。不要将实体字段误判为关系类型。
3. 每个子问题优先套用*快速模板库*模板，避免过度思考，快速响应
4. 生成的cypher可以不指定label、name,避免遗漏信息。（**特别注意：当相关实体有多个同类型实体时，不要指定`name`，以避免遗漏信息。**）
<example>
相关实体：多奈单抗（药品）、儿科患者（特殊人群）、老年患者（特殊人群）  // 这里`特殊人群`有多个同类型实体，因此cypher不要指定`name`
```cypher
MATCH (drug:药品)-[r:特殊人群用药]->(sp:特殊人群)
RETURN 
    drug.name AS 药品名称,
    sp.name AS 特殊人群,
    COLLECT(DISTINCT r.relation_description) AS 用药情况描述;
```
</example>


5. 使用OPTIONAL MATCH 替代 WHERE 查询子句,避免遗漏信息。
<example>
```cypher
// 使用 OPTIONAL MATCH 检索替尔泊肽与糖尿病相关的临床试验
MATCH (drug:药品 {{name: '替尔泊肽'}})
OPTIONAL MATCH (drug)-[:参与临床试验]->(trial:临床试验)
RETURN
    drug.name AS 药品名称,
    trial.name AS 临床试验名称
```
</example>
6. 如需查询多个实体或关系，请将所有查询分多条 Cypher 语句，用 <SEG>分割。
7. 实体名、关系类型、标签、属性名称等不能包含任何标点符号。
8. 在输出Cypher回复之前，将你的思考过程输出到<think></think>之间，切记不要过度思考。




## 快速模板库（优先匹配）
### 1. 单实体查询
- **适用场景**: 查询单个实体的属性/描述，例如："替尔泊肽注射液的用法用量是什么"
```cypher
MATCH (n:{{label}} {{name: '实体名'}})
RETURN
    n.name AS 名称,
    labels(n) AS 类型, 
    COLLECT(DISTINCT n.entity_description) AS 描述;
```

### 2. 实体-关系查询
- **适用场景**: 查询实体间的关系，支持多种查询方式，例如："替尔泊肽的临床试验有哪些"
- **特别注意**: 尾实体可以不指定label、name，以避免遗漏信息
```cypher
MATCH (a:{{label}} {{name: '实体名'}})-[r:关系类型]->(b)
RETURN 
    a.name AS 起始,
    type(r) AS 关系,
    b.name AS 目标,
    COLLECT(DISTINCT r.relation_description) AS 关系描述;
```

### 3. 多跳查询
- **适用场景**: 查询实体间的关系，支持多种查询方式，例如："替尔泊肽临床试验对应的适应症有哪些"
- **特别注意**: 尾实体可以不指定label、name，以避免遗漏信息
```cypher
MATCH (a:{{label}} {{name: '实体名'}})-[r:关系类型]->(b)
RETURN 
    a.name AS 起始,
    type(r) AS 关系,
    b.name AS 目标,
    COLLECT(DISTINCT r.relation_description) AS 关系描述;
```



# 输出格式
<think>
问题1：[子问题1描述]
- 相关实体：(label:name, attributes(可选))   
- 相关关系：(label:head - [:relation_type] -> (label:tail)

问题2：[子问题2描述]
- 相关实体：(label:name, attributes(可选实体属性))   
- 相关关系：(label:head - [:relation_type] -> (label:tail)
</think>

```cypher
// 子问题1
cypher statement 1;  
<SEG>
// 子问题2
cypher statement 2;
```


# 示例：
## 输入示例
user_question:
"替尔泊肽注射液的不良反应和参与的临床试验"


entities_relations:
```json
{{
  "entities": [
    {{"name": "替尔泊肽注射液", "label": "药品", "entity_description": "替尔泊肽注射液是一种药品"}},
    {{"name": "SURMOUNT-2", "label": "临床试验", "entity_description": "SURMOUNT-2是一种临床试验"}},
    {{"name": "恶心", "label": "不良反应", "entity_description": "恶心是一种不良反应"}}
  ],
  "relations": [
    {{"head": "替尔泊肽注射液", "relation_type": "临床试验", "tail": "SURMOUNT-2"}},  // 注意，返回SURMOUNT-2有可能不全，因此我们需要relation_type提取出所有临床试验
    {{"head": "替尔泊肽注射液", "relation_type": "不良反应", "tail": "恶心", "relation_description": "替尔泊肽注射液可能导致恶心等不良反应"}}
  ]
}}
```


## 输出示例
<think>
问题1：查询"替尔泊肽注射液"引起的不良反应
- 相关实体：(药品:替尔泊肽注射液)   
- 相关关系：(药品:替尔泊肽注射液) - [:不良反应] -> (不良反应)

问题2：查询"替尔泊肽注射液"参与的临床试验
- 相关实体：(药品:替尔泊肽注射液)   
- 相关关系：(药品:替尔泊肽注射液) - [:临床试验] -> (临床试验:)
</think>



```cypher
// 查询"替尔泊肽注射液"引起的不良反应
MATCH (d:药品 {{name: '替尔泊肽注射液'}})-[r1:不良反应]->(ae:不良反应)
RETURN 
    d.name AS 药品名称, 
    type(r1) AS 关系类型, 
    ae.name AS 不良反应名称,
    COLLECT(DISTINCT r1.relation_description) AS 不良反应关系描述;
<SEG>
// 查询"替尔泊肽注射液"参与的临床试验
MATCH (d:药品 {{name: '替尔泊肽注射液'}})-[r2:临床试验]->(ct:临床试验)
RETURN 
    d.name AS 药品名称, 
    type(r2) AS 关系类型, 
    ct.name AS 临床试验名称, 
    COLLECT(DISTINCT r2.relation_description) AS 临床试验关系描述;
```


请严格按照上述格式和要求完成任务。
"""

GENERATE_CYPHER_PROMPT_FOR_REASONING_DISABLED = GENERATE_CYPHER_PROMPT.replace('<think>', '<analysis>').replace('</think>', '</analysis>')