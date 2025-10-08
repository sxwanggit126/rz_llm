[项目地址](https://github.com/sxwanggit126/pixmo-docs-debug) 
# 基础用法
## 1.生成训练数据
```shell
python main.py -p {管道名称} \
               -t {数据类型} \
               -n {样本数量} \
               -m {数据集名称}
```

###  Mermaid训练数据
```shell
python main.py -p "MermaidDiagramPipeline" \
-n 10 -t "flowchart,sequence diagram,class diagram" \
-m "mermaid_types"
```
## 2.解析parquet训练数据
```shell
# ===================
# 转换特定数据集
# ===================
python convert.py --dataset generate-mermaid-diagrams
```

# 作业安排
- **第一次**: 跑通pixmo-docs项目
- **第二次**: parquet训练数据解析成jsonl格式，所有的内容（图片、qa、topic）都是中文且不乱码
- **第三次**：1.流程：从下到上的、从右到左的 2.流程：多个开始、多个结束