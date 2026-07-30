def openwin():
    import requests
    from PySide6.QtWidgets import QMessageBox

    from videotrans.component.set_form import JiuCaiForm
    from videotrans.configure.config import app_cfg, params
    from videotrans.tts._jiucaiclone import api_base

    winobj = JiuCaiForm()
    app_cfg.child_forms["jiucai"] = winobj

    def values():
        return api_base(winobj.jiucai_api.text()), winobj.jiucai_key.text().strip()

    def save(close=True):
        try:
            url, key = values()
        except Exception as exc:
            QMessageBox.warning(winobj, "配置无效", str(exc))
            return False
        if not key:
            QMessageBox.warning(winobj, "配置无效", "请填写 API Key")
            return False
        params["jiucai_api"] = url
        params["jiucai_key"] = key
        params.save()
        if close:
            winobj.close()
        return True

    def test():
        try:
            url, key = values()
            if not key:
                raise ValueError("请填写 API Key")
            response = requests.get(
                f"{url}/models",
                headers={"Authorization": f"Bearer {key}", "x-api-key": key}, timeout=30,
            )
            if response.status_code in (401, 403):
                raise ValueError("API Key 无效或无权限")
            response.raise_for_status()
            QMessageBox.information(winobj, "测试连接", "连接成功")
        except Exception as exc:
            QMessageBox.warning(winobj, "测试连接", str(exc) if not isinstance(exc, requests.RequestException) else "连接失败")

    winobj.save_api.clicked.connect(lambda: save())
    winobj.test_api.clicked.connect(test)
    winobj.show()
