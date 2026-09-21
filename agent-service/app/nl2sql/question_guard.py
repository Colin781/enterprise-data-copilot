import re

from app.nl2sql.errors import NL2SQLPolicyError


class QuestionGuard:
    _WRITE_SQL = re.compile(
        r"\b(drop|delete|update|insert|alter|truncate|copy|grant|revoke|create)\b",
        re.IGNORECASE,
    )
    _OVERRIDE = re.compile(
        r"\b(ignore|bypass|override)\b.{0,40}\b(instruction|rule|policy|guard)\b",
        re.IGNORECASE,
    )
    _SECRETS = re.compile(
        r"\b(password|credential|secret|api[-_ ]?key|dsn|system prompt)\b",
        re.IGNORECASE,
    )
    _CODE = re.compile(r"\b(exec|eval)\s*\(|\brun\b.{0,20}\bpython\b", re.IGNORECASE)

    def inspect(self, question: str) -> str:
        normalized = " ".join(question.split())
        if not normalized:
            raise NL2SQLPolicyError("EMPTY_QUESTION")
        if len(normalized) > 5_000:
            raise NL2SQLPolicyError("QUESTION_TOO_LONG")
        if self._WRITE_SQL.search(normalized) or re.search(
            r"删除.{0,20}(订单|表|数据)|提高.{0,20}价格|价格.{0,20}提高|修改.{0,20}数据",
            normalized,
        ):
            raise NL2SQLPolicyError("WRITE_REQUEST_NOT_ALLOWED")
        if self._OVERRIDE.search(normalized) or re.search(
            r"忽略.{0,30}(规则|指令|提示)|绕过.{0,20}(规则|检查|限制)", normalized
        ):
            raise NL2SQLPolicyError("SAFETY_OVERRIDE_NOT_ALLOWED")
        if self._SECRETS.search(normalized) or re.search(
            r"密码|系统提示词|密钥|完整.{0,10}连接", normalized
        ):
            raise NL2SQLPolicyError("SECRET_REQUEST_NOT_ALLOWED")
        if re.search(r"其他租户|其它租户|别的租户|跨租户", normalized):
            raise NL2SQLPolicyError("CROSS_TENANT_REQUEST_NOT_ALLOWED")
        if re.search(r"身份证|社会安全号|\bsocial security number\b|\bssn\b", normalized, re.I):
            raise NL2SQLPolicyError("SENSITIVE_DATA_NOT_ALLOWED")
        if self._CODE.search(normalized) or re.search(r"运行.{0,20}Python", normalized, re.I):
            raise NL2SQLPolicyError("ARBITRARY_CODE_NOT_ALLOWED")
        return normalized
