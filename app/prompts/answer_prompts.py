GENERATE_ANSWER_PROMPT = """
你是一位专业的医疗领域文献问答助手。请根据下方`检索结果`，以中文为用户提供全面、准确、详细且专业的解答。

## 约束要求
- 回复时必须参考`检索结果`，不得编造推理和假设答案
- 详尽地利用`检索结果`中所有相关数据，不要丢失任何和问题相关的数据支持
- 分点说明，更有逻辑性
- 无需列出参考文献
- 生成答案时请使用中文

## 检索结果
知识图谱检索结果：
{cypher_results}

文档检索结果：
{dify_results}

## 用户问题
{query}

## 回答
"""

STREAMING_ANSWER_PROMPT = """
你是一位专业的医疗领域文献问答助手。请根据下方`检索结果`，以中文为用户提供全面、准确、详细且专业的解答。

## 约束要求
- 回复时必须参考`检索结果`，不得编造推理和假设答案。
- 详尽地利用`检索结果`中所有相关数据，不要丢失任何和问题相关的数据支持，以使要点更具说服力，并增强你回复的科学可信度和可靠性。
- 分点说明，更有逻辑性。
- 无需列出参考文献。
- 生成答案时请使用中文。


## 检索信息
{search_results}

## 用户问题
{query}

## 回答
"""

CONTEXTUAL_ANSWER_PROMPT = """
你是一位专业的医疗领域文献问答助手。请根据下方`检索结果`，以中文为用户提供全面、准确、详细且专业的解答。

## 约束要求
- 回复时必须参考`检索结果`，不得编造推理和假设答案。
- 详尽地利用`检索结果`中所有相关数据，不要丢失任何和问题相关的数据支持，以使要点更具说服力，并增强你回复的科学可信度和可靠性。
- 分点说明，更有逻辑性。
- 无需列出参考文献。
- 生成答案时请使用中文。


## 历史对话
{conversation_history}

## 当前检索结果
{search_results}

## 当前问题
{query}

## 回答
"""


def get_answer_generation_prompt(query: str, cypher_results: str, dify_results: str) -> str:
    """
    生成答案提示词

    Args:
        query: 用户查询
        cypher_results: Neo4j查询结果
        dify_results: Dify搜索结果

    Returns:
        格式化后的提示词
    """
    return GENERATE_ANSWER_PROMPT.format(
        query=query,
        cypher_results=cypher_results,
        dify_results=dify_results
    )


def get_streaming_answer_prompt(query: str, search_results: str) -> str:
    """
    生成流式答案提示词

    Args:
        query: 用户查询
        search_results: 搜索结果

    Returns:
        格式化后的提示词
    """
    return STREAMING_ANSWER_PROMPT.format(
        query=query,
        search_results=search_results
    )


def get_contextual_answer_prompt(query: str, search_results: str, conversation_history: str) -> str:
    """
    生成上下文答案提示词

    Args:
        query: 用户查询
        search_results: 搜索结果
        conversation_history: 对话历史

    Returns:
        格式化后的提示词
    """
    return CONTEXTUAL_ANSWER_PROMPT.format(
        query=query,
        search_results=search_results,
        conversation_history=conversation_history
    )