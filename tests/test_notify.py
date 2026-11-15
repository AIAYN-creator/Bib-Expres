"""El aviso del sistema: que los textos (con titulos de papers de una API externa)
nunca acaben dentro de un script, y que el XML de Windows vaya escapado."""

import xml.dom.minidom

from bib_expres.gui import notify


def test_toast_xml_escapes_everything():
    xml_text = notify.toast_xml('Busqueda <terminada> & "ok"', "Title with </text><script>x</script>")
    doc = xml.dom.minidom.parseString(xml_text)  # XML valido
    texts = [n.firstChild.data for n in doc.getElementsByTagName("text")]
    assert texts == ['Busqueda <terminada> & "ok"', "Title with </text><script>x</script>"]
    assert doc.getElementsByTagName("script") == []


def test_windows_command_keeps_data_out_of_the_script():
    hostile = "'; Remove-Item C:\\ -Recurse; '$(calc)`"
    cmd, env = notify.windows_command(hostile, hostile)
    script = cmd[-1]
    assert hostile not in script and "calc" not in script
    assert "$env:BIBEXPRES_TOAST_XML" in script
    assert "calc" in env["BIBEXPRES_TOAST_XML"]
    assert env["BIBEXPRES_TOAST_APPID"] == notify.APP_ID


def test_mac_and_linux_pass_text_as_arguments():
    hostile = '" & do shell script "rm -rf ~" & "'
    mac = notify.mac_command("t", hostile)
    assert mac[-1] == hostile and all(hostile not in part for part in mac[:-2])
    assert notify.linux_command("t", hostile)[-1] == hostile


def test_long_text_is_clipped():
    body = notify.toast_xml("t", "x" * 1000)
    assert len(body) < 400


def test_notify_never_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("no powershell")

    monkeypatch.setattr(notify.subprocess, "Popen", boom)
    assert notify.notify("t", "b") is False
