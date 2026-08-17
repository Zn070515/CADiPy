# 错误语义

公共错误继承 `CadipyError`，通过稳定 `code`、operation 和 details 传递机器可读证据。类型包括参数、平台/版本、目标绑定、COM、rebuild、verification、文件和协议错误。

后端 HRESULT、SOLIDWORKS 返回码和原始异常链只留在诊断上下文，不直接成为 API/RPC 的错误契约。
