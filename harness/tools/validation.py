from jsonschema import Draft202012Validator

def reject_external_refs(value) -> None:
    """禁止自动解析外部 $ref，避免校验阶段意外访问外部资源。"""
    if isinstance(value , dict):
        ref = value.get("$ref")
        if isinstance(ref , str) and not ref.startswith('#'):
            raise ValueError(f"禁止外部 JSON Schema 引用：{ref}")
        
        for child in value.values():
            reject_external_refs(child)
    elif isinstance(value , list):
        for child in value:
            reject_external_refs(child)

def validate_tool_arguments(schema : dict , arguments : dict) -> None:
    """ 验证工具参数 """
    reject_external_refs(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(arguments) , key=lambda error : list(error.path))

    if not errors:
        return
    
    error = errors[0]

    path = ".".join([str(index) for index in error.path])
    raise ValueError(f"参数 '{path}' 不合法：{error.message}" if path else f"工具参数不合法：{error.message}")
















    