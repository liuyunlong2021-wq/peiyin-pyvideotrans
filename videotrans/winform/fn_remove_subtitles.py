from videotrans.configure.config import app_cfg
from videotrans.winform.fn_production_project import ProductionProjectWindow


def openwin():
    window = ProductionProjectWindow(remove_only=True)
    app_cfg.child_forms["fn_remove_subtitles"] = window
    window.show()
