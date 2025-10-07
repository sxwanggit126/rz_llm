"""
评估用的Prompt模板
"""

# Zero-shot直接分类
zero_shot_prompt = """请根据问题选择最合适的答案。

问题：{question}

选项：
A. {choice_a}
B. {choice_b}
C. {choice_c}
D. {choice_d}

请直接回答A、B、C或D。"""

# Zero-shot思维链
zero_shot_cot_prompt = """请根据问题选择最合适的答案，并详细说明你的推理过程。

问题：{question}

选项：
A. {choice_a}
B. {choice_b}
C. {choice_c}
D. {choice_d}

请按以下格式回答：
分析：[详细的推理过程]
答案：[A、B、C或D]"""

# Few-shot固定示例
few_shot_examples = [
    {
        "question": "水的化学分子式是什么？",
        "choices": ["CO2", "H2O", "NaCl", "CH4"],
        "answer": "B",
        "explanation": "水是由两个氢原子和一个氧原子组成的化合物"
    },
    {
        "question": "太阳系中最大的行星是？",
        "choices": ["地球", "木星", "土星", "火星"],
        "answer": "B",
        "explanation": "木星是太阳系中质量和体积最大的行星"
    },
    {
        "question": "下列哪个不是编程语言？",
        "choices": ["Python", "Java", "HTML", "C++"],
        "answer": "C",
        "explanation": "HTML是标记语言，不是编程语言"
    }
]

few_shot_prompt = """以下是一些示例：

示例1：
问题：水的化学分子式是什么？
选项：
A. CO2
B. H2O  
C. NaCl
D. CH4
答案：B

示例2：
问题：太阳系中最大的行星是？
选项：
A. 地球
B. 木星
C. 土星  
D. 火星
答案：B

示例3：
问题：下列哪个不是编程语言？
选项：
A. Python
B. Java
C. HTML
D. C++
答案：C

现在请回答下面的问题：

问题：{question}

选项：
A. {choice_a}
B. {choice_b}
C. {choice_c}
D. {choice_d}

请直接回答A、B、C或D。"""

# Few-shot思维链
few_shot_cot_prompt = """以下是一些示例：

示例1：
问题：水的化学分子式是什么？
选项：
A. CO2
B. H2O  
C. NaCl
D. CH4
分析：水是由氢原子和氧原子组成的化合物。CO2是二氧化碳，NaCl是氯化钠（盐），CH4是甲烷。只有H2O表示水分子，由2个氢原子和1个氧原子组成。
答案：B

示例2：
问题：太阳系中最大的行星是？
选项：
A. 地球
B. 木星
C. 土星  
D. 火星
分析：太阳系的行星按大小排序：木星是最大的，然后是土星、海王星、天王星、地球、金星、火星、水星。木星的质量比其他所有行星加起来还要大。
答案：B

示例3：
问题：下列哪个不是编程语言？
选项：
A. Python
B. Java
C. HTML
D. C++
分析：Python、Java和C++都是编程语言，可以用来编写程序逻辑。HTML是超文本标记语言，用于创建网页结构，属于标记语言而不是编程语言。
答案：C

现在请回答下面的问题：

问题：{question}

选项：
A. {choice_a}
B. {choice_b}
C. {choice_c}
D. {choice_d}

请按以下格式回答：
分析：[详细的推理过程]
答案：[A、B、C或D]"""

# 翻译用的Prompt
translation_prompt = """请将以下英文内容翻译成中文，保持原意和准确性：

原文：{text}

翻译："""