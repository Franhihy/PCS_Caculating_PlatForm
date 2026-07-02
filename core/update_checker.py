import json
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class UpdateChecker(QObject):
    update_available = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)

    def check(self, update_url, current_version):
        req = QNetworkRequest(QUrl(update_url))
        req.setTransferTimeout(8000)
        reply = self._manager.get(req)
        reply.finished.connect(lambda: self._on_reply(reply, current_version))

    def _on_reply(self, reply, current_version):
        try:
            if reply.error() != QNetworkReply.NoError:
                reply.deleteLater()
                return
            data = bytes(reply.readAll()).decode('utf-8')
            info = json.loads(data)
            remote_ver = info.get('version', '0.0.0')
            if self._is_newer(remote_ver, current_version):
                self.update_available.emit(info)
        except Exception:
            pass
        finally:
            reply.deleteLater()

    @staticmethod
    def _is_newer(remote, local):
        try:
            r = tuple(int(x) for x in remote.split('.'))
            l = tuple(int(x) for x in local.split('.'))
            return r > l
        except Exception:
            return False
