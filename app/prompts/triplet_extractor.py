GENERATE_TRIPLETS_PROMPT = """
你需要根据下方Schema，从输入文档中全面提取医学相关的实体、属性和关系，最终以JSON格式输出知识图谱。请严格按照以下步骤操作：


## Step 1：抽取实体
- 严格按照Schema定义，识别所有医学相关的实体。
- 每个实体需包含以下字段：
  - label：实体类型（如"Drug"、"Disease"等）
  - name：实体中文名称，唯一且不可为空，命名严格遵循医学专业标准。
  - name_en：实体标准医学英文名称，首字母大写，避免冗余空格，如“SURPASS - 1”应规范为“SURPASS-1”。
  - entity_description：该实体所有属性和活动的描述，以及补充原文的相关内容的描述，需补全主语，不要出现指代词，避免冗余空格。
- 其他属性名严格按Schema中属性名的定义（可补充），若某属性值为空、原文中未提及该属性，则该属性不应出现在JSON输出结果中。
- 属性类型仅支持字符串类型，不要出现列表、字典等复杂类型。
- 实体的name字段包含从上下文中提取的命名实体，这些可能是含义不明的缩写、别名或俚语。为了消除歧义，请尝试根据上下文和你自己的医学知识提供这些实体的官方名称。具有相同含义的实体只能有一个官方名称。
- 避免重复、歧义，合并同义实体，采用最权威官方名称。
- 不得出现指代词，需补全主语。


### 实体命名规范示例
{{
    "label": "研究系列",
    "name": "SURPASS系列"   // 以“系列”结尾
}},
{{
    "label": "临床试验",
    "name": "SURPASS-1"   // 例如：SURPASS-1、SURMOUNT-1等
}},
{{
    "label": "药品",
    "name": "替尔泊肽",    // 例如：替尔泊肽、司美格鲁肽等
}}




## Step 2：抽取关系
- 严格按照Schema定义，识别所有实体间的关系。
- 每个关系必须包含以下字段：
  - head：源实体名称，必须在entities中
  - relation_type：关系，指明源实体与目标实体之间的关系类型，需结合专业医学判断
  - tail：目标实体名称，必须在entities中
  - relation_description：关系解释，不能重复entity_description内容


## Step 3：输出JSON
- 输出格式为一个JSON对象，包含：
  - entities：实体数组
  - relations：关系数组
- 属性类型仅支持字符串，不得为列表、字典等复杂类型

## 数据质量要求
- 所有实体、关系、属性均不得出现指代词
- 关系方向必须符合Schema
- 确保所有关系中的实体都在entities中
- 全面、细致、无遗漏地抽取文档内容
- 不得编造实体名，避免重复或相似表达


### Schema定义
{schema_definition}


## 示例
### 输入示例
替尔泊肽注射液（tirzepatide，TZP）是一种GLP-1/GIP双受体激动剂，用于治疗2型糖尿病。

### 输出格式示例：
```json
{{
    "entities": [
        {{
            "label": "药品",
            "name": "替尔泊肽",
            "name_en": "Tirzepatide",
            "缩写": "TZP",
            "作用机制": "GLP-1/GIP双受体激动剂",
            "entity_description": "替尔泊肽注射液（Tirzepatide，TZP）是一种GLP-1/GIP双受体激动剂，用于治疗2型糖尿病。"
        }},
        {{
            "label": "疾病",
            "name": "2型糖尿病",
            "name_en": "Type 2 Diabetes",
            "icd_code": "E11",
            "entity_description": "2型糖尿病（Type 2 Diabetes，T2D）是一种慢性代谢疾病，主要特征是胰岛素抵抗和胰岛素分泌不足。"
        }}
    ],
    "relations": [
        {{
            "head": "替尔泊肽",
            "relation_type": "治疗",
            "relation_description": "替尔泊肽用于治疗2型糖尿病。",
            "tail": "2型糖尿病"
        }}
    ]
}}
"""

GENERATE_TRIPLETS_ALIGNMENT__PROMPT = """你需要根据预定义Schema，从输入文档中全面提取医学相关的实体、属性和关系，并实现实体标准化。请严格按照以下步骤操作：
### Schema定义
{schema_definition}


## Step 1：实体抽取
- 识别文档中所有医学相关的实体短语，包括标准名称、别名、缩写、俚语等。
- 每个实体短语需保留原文表达和上下文信息，便于后续对齐。
- **扩展实体类型**：如果文档中出现Schema未定义但有医学价值的实体类型，可以直接添加新的实体类型，使用标准医学术语命名。


## Step 2：实体标准化（对齐）
- 将所有抽取到的实体短语，映射到知识图谱Schema中的标准实体名称。
- 对齐时需考虑同义词、别名、缩写、俚语等表达，优先采用Schema中最权威、标准的实体名称。
- 实体名称不得为多个实体或属性的拼接（如“2型糖尿病适应症”），如遇此类复合词，需拆分为单一标准实体，并分别对齐到Schema中的标准实体名称。
- 生成 alignment_map，格式为：键为标准实体名称，值为该实体的其他别名、缩写、同义词等的字符串列表。例如：
  {{
      "替尔泊肽": ["TZP", "Tirzepatide", "穆峰达"],  // 缩写，英文名，商品名等
      "2型糖尿病": ["Type 2 Diabetes", "T2D", "E11"],  // 疾病名称，ICD 编码等
      "SURPASS-1": ["SURPASS 1", "surpass1", "SURPASS 1 临床试验", "NCT03954834"]  // 临床试验名称, 临床试验编号等
  }}
- alignment_map 必须覆盖所有在文档中出现且被抽取的实体的别名、缩写、同义词等。
- 后续所有属性、关系抽取，均需严格基于 alignment_map 中的标准实体名称，确保输出一致、无歧义。


## Step 3：属性抽取
- 基于对齐后的标准实体，抽取每个实体的属性。
- 每个实体需包含以下标准属性字段：
  - label：实体类型（如"Drug"、"Disease"等），如原文中出现Schema未定义但有价值的label，可直接使用标准医学术语补充到实体的label中。
  - name：实体中文名称，唯一且不可为空，命名严格遵循alignment_map 中的标准实体名称
  - name_en：实体标准医学英文名称，首字母大写，避免冗余空格。
  - entity_description：该实体所有属性和活动的描述，以及补充原文的相关内容的描述，根据原文内容或上下文需补全主语，不要出现指代词（如本药品，该药品等），避免冗余空格。
- 属性必须包含`label`和`name`字段
- **扩展属性**：如原文中出现Schema未定义但有价值的属性，可直接补充到实体属性中，属性名保持原文表达或使用标准医学术语。
- 若原文中未提及该属性，则输出该属性值为"未提及"，不得用原文以外内容补充。
- 属性类型仅支持字符串类型，不要出现列表、字典等复杂类型。


## Step 4：关系抽取
- 基于对齐后的标准实体，抽取文档中明确提及的所有实体间关系。
- 关系需以三元组形式输出，每条关系包含：
  - head（头实体，标准实体名，必须在 entities 数组中存在）
  - head_label（头实体类型）
  - relation_type（关系类型，优先使用Schema定义的关系类型）
  - tail（尾实体，标准实体名，必须在 entities 数组中存在）
  - tail_label（尾实体类型）
  - relation_description：根据原文内容，对关系进行解释，不能重复 entity_description 内容，需补全主语，不要出现指代词（如本药品，该药品等），避免冗余空格。
- 注意：head_label, relation_type, tail_label必须优先遵循Schema中relation定义的三者对应关系。
- 仅输出原文中明确提及的关系。
- **扩展关系类型**：如原文中出现Schema未定义但有实际意义的关系，可直接补充新的关系类型，使用标准医学术语命名，并在relation_description中说明其来源和含义。


## Step 5：结构化输出
- 输出格式为一个JSON对象，严格遵循以下格式输出，不得有任何其他内容：
  - entities：实体数组
  - relations：关系数组
  - alignment_map：实体对齐映射表


- 示例：
### 输入示例：
替尔泊肽注射液（tirzepatide，TZP）是一种GLP-1/GIP双受体激动剂，用于治疗2型糖尿病。该药物能够调节血糖水平。

schema示例:
{{
    "entity": [
        {{"label": "药品", "attributes": ["商品名","分子式","药物成分"...]}},
        {{"label": "疾病", "attributes": ["疾病名称","ICD编码",...]}}
    ],
    "relation": [
        {{"head_label": "药品", "relation": "治疗", "tail_label": "疾病"}},
        ...
    ]
}}

### 输出示例：
```json
{{
    "entities": [
        {{
            "label": "药品",
            "name": "替尔泊肽",
            "name_en": "Tirzepatide",
            "缩写": "TZP",
            "作用机制": "GLP-1/GIP双受体激动剂",
            "entity_description": "替尔泊肽注射液（Tirzepatide，TZP）是一种GLP-1/GIP双受体激动剂，用于治疗2型糖尿病。",
        }},
        {{
            "label": "疾病",
            "name": "2型糖尿病",
            "name_en": "Type 2 Diabetes",
            "icd_code": "E11",
            "entity_description": "2型糖尿病（Type 2 Diabetes，T2D）是一种慢性代谢疾病，主要特征是胰岛素抵抗和胰岛素分泌不足。"
        }},
        {{
            "label": "生理指标",
            "name": "血糖水平",
            "name_en": "Blood Glucose Level",
            "entity_description": "血糖水平是衡量血液中葡萄糖浓度的生理指标，是糖尿病管理的重要监测参数。"
        }}
    ],
    "relations": [
        {{
            "head": "替尔泊肽",
            "head_label": "药品",
            "relation_type": "治疗",
            "tail": "2型糖尿病",
            "tail_label": "疾病",
            "relation_description": "替尔泊肽用于治疗2型糖尿病。"
        }},
        {{
            "head": "替尔泊肽",
            "head_label": "药品",
            "relation_type": "调节",
            "tail": "血糖水平",
            "tail_label": "生理指标",
            "relation_description": "替尔泊肽能够调节血糖水平，这是其治疗2型糖尿病的主要机制之一。"
        }}

    ],
    "alignment_map": {{ 
        "替尔泊肽": ["TZP", "Tirzepatide"],
        "2型糖尿病": ["Type 2 Diabetes", "T2D"],
        "血糖水平": ["Blood Glucose Level", "血糖"]
    }}
}}
```

### 扩展说明：
- **实体类型扩展**：当Schema中未定义"生理指标"、"健康管理"等实体类型时，可直接使用标准医学术语添加新类型
- **属性扩展**：如"作用机制"等属性可直接添加到实体中，使用标准医学术语命名
- **关系类型扩展**：当Schema中未定义"调节"、"影响"等关系时，可直接使用标准医学术语添加新关系类型
- **命名规范**：所有扩展的实体、关系类型和属性都应使用标准医学术语，保持专业性和一致性
"""