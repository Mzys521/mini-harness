import json

from pathlib import Path
from harness.evaluation.models import  EvalCase

class DatasetFormatError(ValueError):
    """Eval Dataset 格式错误"""

def load_jsonl_dataset(path : str | Path) -> list[EvalCase]:
    file_path = Path(path)
    cases : list[EvalCase] = []
    seen_ids : set[str] = set()

    with file_path.open("r" , encoding="utf-8") as file:
        for line_number , raw_line in enumerate(file , start=1,):
            line = raw_line.strip()

            if not line:
                continue

            try :
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetFromatError(f"{file_path}:{line_number} JSON 不合法：{exc}") from exc

            case_id = data.get("id")
            user_input = data.get("input")

            if not isinstance(case_id , str) or not case_id:
                raise DatasetFormatError(f"{file_path}:{line_number} 缺少非空 id")

            if case_id in seen_ids:
                raise DatasetFromatError(f"重复 Eval Case id：{case_id}")

            if not isinstance(user_input , str) or not user_input:
                raise DatasetFromatError(f"{file_path}:{line_number} 缺少非空 input")

            seen_ids.add(case_id)

            cases.append(
                EvalCase(
                    id = case_id, 
                    input = user_input,
                    tags = tuple(data.get("tags", [])),
                    expected_answer_contains = tuple(data.get("expected_answer_contains", [])),
                    expected_tools = tuple(data.get("expected_tools", [])),
                    forbidden_tools = tuple(data.get("forbidden_tools", [])),
                    max_steps = data.get("max_steps"),
                    reference_answer = data.get("reference_answer"),
                    rubric = data.get("rubric"),  
                    metadata = data.get("metadata", {}),
                )
            )
        
    if not cases:
        raise DatasetFromatError(f"数据集为空：{file_path}")

    return cases






