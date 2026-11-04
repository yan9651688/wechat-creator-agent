# 数稿子的句子形状：每句平均几个逗号、平均多少字，对照『你自己的改稿』参考线（默认值是一组示例，攒够自己的改稿后在下面改）
# 用法：python3 -I 句子形状.py <文章 md>...
# 不算标题、小标题、图片、表格、引用块和 ``` 围栏（提示词）；按句号、问号、感叹号断句
import re
import sys

# 参考线：AI 初稿通常每句 1.2～1.8 个逗号、29 字左右；人改过的稿子通常更长更绕。下面数字是示例，按你自己的改稿统计后替换
LOW_COMMA, LOW_LEN = 2, 35
HIGH_COMMA, HIGH_LEN = 4.9, 63

for path in sys.argv[1:]:
    text = open(path, encoding='utf-8').read()
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    lines = [l for l in text.splitlines()
             if l.strip() and not l.lstrip().startswith(('#', '!', '|', '>'))]
    sents = [s for s in re.split(r'[。？！?!]+', '\n'.join(lines))
             if len(re.sub(r'\s', '', s)) > 3]
    if not sents:
        print(f'{path}：没有可数的句子')
        continue
    commas = sum(s.count('，') for s in sents) / len(sents)
    length = sum(len(re.sub(r'\s', '', s)) for s in sents) / len(sents)
    if commas < LOW_COMMA or length < LOW_LEN:
        note = '偏短，句子形状还像 AI，再改一轮'
    elif commas > HIGH_COMMA or length > HIGH_LEN:
        note = '超过参考线上限，看一眼有没有硬接的句子'
    else:
        note = '在参考线范围里'
    print(f'{path}：{len(sents)} 句，每句 {commas:.2f} 个逗号，{length:.1f} 字，{note}')
