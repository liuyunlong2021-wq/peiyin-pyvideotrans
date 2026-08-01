def openwin():
    from pathlib import Path
    from videotrans.configure.config import ROOT_DIR,tr,app_cfg,params
    from videotrans.configure import config
    from videotrans.util import tools
    from videotrans.util.ListenVoice import ListenVoice
    from videotrans.component.set_form import QwenttsLocalForm
    from PySide6.QtCore import QThread, Signal

    winobj = QwenttsLocalForm()
    app_cfg.child_forms['qwenttslocal'] = winobj

    class DownloadThread(QThread):
        done = Signal(str)

        def __init__(self, model):
            super().__init__(winobj)
            self.model = model

        def run(self):
            try:
                from videotrans.tts._qwenttslocal import download_qwen_base
                download_qwen_base(self.model)
                self.done.emit('ok')
            except Exception as error:
                self.done.emit(str(error))

    def feed(d):
        if d == "ok":
            from PySide6 import QtWidgets
            QtWidgets.QMessageBox.information(winobj, "ok", "Test Ok")
        else:
            tools.show_error(d)
        winobj.test.setText(tr('Test'))

    def test():
        params["qwenttslocal_prompt"] = winobj.instruct_text.text()
        params["qwenttslocal_model"] = winobj.model.currentText()
        params.save()
        _rolename = next(reversed(tools.get_f5tts_role().values()))
        if not isinstance(_rolename,dict):
            return tools.show_error(tr("No reference audio {} exists",_rolename))
        rolename=_rolename.get('ref_wav')
        file=ROOT_DIR+f'/f5-tts/{rolename}'
        if not Path(file).exists():
            return tools.show_error(tr("No reference audio {} exists",file))
        from videotrans import tts
        import time
        winobj.test.setText(tr('Testing...')+f'  {rolename}')
        wk = ListenVoice(parent=winobj, queue_tts=[{
            "text": '\u4f60\u597d\u554a\u6211\u7684\u670b\u53cb,\u5e0c\u671b\u4f60\u7684\u6bcf\u4e00\u5929\u90fd\u7f8e\u597d\u6109\u5feb',
            "role": rolename,
            "filename": config.TEMP_DIR + f"/{time.time()}-qwenttslocal.wav",
            "tts_type": tts.QWEN3LOCAL_TTS}],
                         language="zh-cn",
                         tts_type=tts.QWEN3LOCAL_TTS)
        wk.uito.connect(feed)
        wk.start()

    def save():
        params["qwenttslocal_prompt"] = winobj.instruct_text.text()
        params["qwenttslocal_model"] = winobj.model.currentText()
        params.save()
        tools.set_process(text='', type="refreshtts")
        winobj.close()

    def download():
        model = winobj.model.currentText()
        params["qwenttslocal_model"] = model
        params.save()
        winobj.download.setDisabled(True)
        winobj.download.setText(('正在下载 ' if config.defaulelang == 'zh' else 'Downloading ') + model)
        worker = DownloadThread(model)
        winobj.download_worker = worker

        def finished(result):
            from PySide6.QtWidgets import QMessageBox
            winobj.download.setDisabled(False)
            winobj.download.setText('下载所选模型' if config.defaulelang == 'zh' else 'Download selected model')
            if result == 'ok':
                QMessageBox.information(winobj, 'OK', model + (' 下载完成' if config.defaulelang == 'zh' else ' downloaded'))
            else:
                tools.show_error(result)

        worker.done.connect(finished)
        worker.start()

    if params.get("qwenttslocal_prompt"):
        winobj.instruct_text.setText(params.get("qwenttslocal_prompt"))
    winobj.model.setCurrentText(params.get("qwenttslocal_model", "0.6B"))
    winobj.save.clicked.connect(save)
    winobj.download.clicked.connect(download)
    winobj.test.clicked.connect(test)
    winobj.show()
