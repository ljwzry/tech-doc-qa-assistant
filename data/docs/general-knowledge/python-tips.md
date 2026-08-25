# Python 开发技巧

## 虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate
```

## 类型提示

使用类型提示提高代码可读性和IDE支持：
```python
def process(data: List[str]) -> Dict[str, int]:
    pass
```
