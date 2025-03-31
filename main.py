import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

import captcha


NCA_URL = "https://nca.pki.gov.kz/service/pkiorder/create.xhtml?lang=ru&certtemplateAlias=individ_ng"


def validate_user_input(iin: str) -> tuple[bool, str | None]:
    is_valid = True
    error_msg = None
    if len(iin) != 12 or not iin.isdecimal():
        is_valid = False
        error_msg = "ИИН должен состоять из 12 цифр (0..9)"
    elif int(iin[11]) != checksum(iin[:11]):
        is_valid = False
        error_msg = "Не сходится контрольная сумма цифр ИИН"
    return is_valid, error_msg


def checksum(iin_11: str) -> int:
    check_nums = (
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        (3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2),
    )
    check_digit = sum([int(x) * y for (x, y) in zip(iin_11, check_nums[0])]) % 11
    if check_digit == 10:
        check_digit = sum([int(x) * y for (x, y) in zip(iin_11, check_nums[1])]) % 11
    return check_digit


def check_iin_nca(iin: str):
    nca_name = None
    user_agent = UserAgent().random
    with requests.Session() as session:
        captcha_data, captcha_error = get_captcha_from_nca(
            session=session, user_agent=user_agent
        )
        if captcha_error["code"] != 0:
            nca_error = {
                "function": "get_captcha_from_nca",
                "code": captcha_error["code"],
                "details": captcha_error["details"],
            }
            return nca_name, nca_error

        nca_name, nca_name_error = get_name_from_nca(
            session=session,
            user_agent=user_agent,
            captcha_data=captcha_data,
            iin=iin,
        )
        if nca_name_error["code"] != 0:
            nca_error = {
                "function": "get_name_from_nca",
                "code": nca_name_error["code"],
                "details": nca_name_error["details"],
            }
            return nca_name, nca_error

        nca_error = {"function": None, "code": 0, "details": None}
        return nca_name, nca_error


def get_captcha_from_nca(
    session: requests.Session, user_agent: str
) -> tuple[dict, dict]:
    captcha_data = {"image_base64": None, "viewstate": None}
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "ru-RU,kk-KZ;q=0.9,en-US;q=0.8",
        "Connection": "keep-alive",
        "Host": "nca.pki.gov.kz",
        "Referer": "https://nca.pki.gov.kz/",
        "User-Agent": user_agent,
    }
    try:
        with session.get(url=NCA_URL, headers=headers) as response:
            status_code = response.status_code
            page = response.text

    except Exception as err:
        captcha_error = {"code": 1, "details": f"{type(err).__name__}: {err}"}
        return captcha_data, captcha_error

    if status_code != 200:
        captcha_error = {
            "code": 2,
            "details": f"HTTP response status code: {status_code}",
        }
        return captcha_data, captcha_error

    soup = BeautifulSoup(markup=page, features="html.parser")
    captcha_element = soup.find(name="span", id="captchaImage")
    if not captcha_element:
        captcha_error = {
            "code": 3,
            "details": "Captcha element not found on the NCA page",
        }
        return captcha_data, captcha_error

    viewstate_element = soup.find(name="input", id="j_id1:javax.faces.ViewState:0")
    if not viewstate_element:
        captcha_error = {
            "code": 4,
            "details": "ViewState element not found on the NCA page",
        }
        return captcha_data, captcha_error

    img_src = captcha_element.find("img")["src"]
    captcha_data["image_base64"] = img_src.removeprefix("data:image/png;base64,")
    captcha_data["viewstate"] = viewstate_element["value"]
    captcha_error = {"code": 0, "details": None}
    return captcha_data, captcha_error


def get_name_from_nca(
    session: requests.Session,
    user_agent: str,
    captcha_data: dict,
    iin: str,
) -> tuple[str | None, dict]:
    nca_name = None
    headers = {
        "Accept": "application/xml, text/xml, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "ru-RU,kk-KZ;q=0.9,en-US;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Faces-Request": "partial/ajax",
        "Origin": "https://nca.pki.gov.kz",
        "Referer": NCA_URL,
        "User-Agent": user_agent,
        "X-Requested-With": "XMLHttpRequest",
    }
    captcha_text = captcha.captcha_base64_to_text(captcha_data["image_base64"])
    data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "rcfield:0:checkPersonButton",
        "javax.faces.partial.execute": "indexForm",
        "javax.faces.partial.render": "indexForm",
        "rcfield:0:checkPersonButton": "rcfield:0:checkPersonButton",
        "indexForm": "indexForm",
        "captcha": captcha_text,
        "rcfield:0:inputValue": iin,
        "connectionpoint": "",
        "userAgreementCheckHidden": "true",
        "certrequestStr": "",
        "keyidStr": "",
        "javax.faces.ViewState": captcha_data["viewstate"],
    }
    try:
        with session.post(
            url=NCA_URL,
            headers=headers,
            data=data,
        ) as response:
            status_code = response.status_code
            xml = response.text
    except Exception as err:
        nca_name_error = {"code": 1, "details": f"{type(err).__name__}: {err}"}
        return nca_name, nca_name_error

    if status_code != 200:
        nca_name_error = {
            "code": 2,
            "details": f"HTTP response status code: {status_code}",
        }
        return nca_name, nca_name_error

    xml_soup = BeautifulSoup(markup=xml, features="xml")
    html = xml_soup.find("update", id="indexForm")

    if not html:
        nca_name_error = {
            "code": 3,
            "details": "indexForm element not found on the NCA page",
        }
        return nca_name, nca_name_error

    html_soup = BeautifulSoup(markup=html.string, features="html.parser")
    alert = html_soup.find("li", role="alert")

    if alert:
        alert_message = alert.find("span", class_="ui-messages-error-summary").string
        nca_name_error = {"code": 4, "details": alert_message}
        if alert_message == "Неправильно указан код с картинки":
            nca_name_error = {"code": 5, "details": alert_message}
        if alert_message.startswith("Проверяемый ИИН (") and alert_message.endswith(
            "), указаный в Вашем запросе, не найден в Государственной Базе Данных Физических Лиц (ГБД ФЛ). Пожалуйста, укажите запрос с правильным ИИН."
        ):
            nca_name_error = {"code": 6, "details": alert_message}
        return nca_name, nca_name_error

    recipient = html_soup.find("span", class_="recipient")
    if recipient:
        nca_name = recipient.string
    nca_name_error = {"code": 0, "details": None}
    return nca_name, nca_name_error


def main():
    ## Примеры ИИН для проверки:
    # iin = "0123456789"  # не 12 цифр в ИИН (невалидный ИИН)
    # iin = "o12345012345"  # недопустимые символы в ИИН (невалидный ИИН)
    # iin = "001122334455"  # не сходится контрольная сумма цифр (невалидный ИИН)
    iin = "980109050588"  # ИИН активен
    # iin = "991223050176"  # ИИН активен (человек без фамилии и отчества, есть только имя)
    # iin = "000101051361"  # ИИН активен (человек без имени и отчества, есть только фамилия)
    # iin = "980109052990"  # ИИН не используется (ещё не выдан)
    # iin = "760405050511"  # ИИН иностранца аннулирован!
    # iin = "920515450074"  # ИИН умершего гражданина РК

    print("==============================")
    print(f"ИИН: {iin}")

    is_valid, error_msg = validate_user_input(iin)
    if not is_valid:
        print("Введено некорректное значение!")
        print(error_msg)
        return

    nca_name, nca_error = check_iin_nca(iin)

    if nca_error["code"] == 0:
        print("Всё ОК, ИИН существует в базе ГБД ФЛ (не аннулирован)!")
        print(f"Имя: {nca_name}")
    elif nca_error["function"] == "get_name_from_nca" and nca_error["code"] == 6:
        print("ИИН не существует или был аннулирован!")
    else:
        print(f"Ошибка при выполнении {nca_error['function']}")
        print(f"Код ошибки: {nca_error['code']}")
        print(nca_error["details"])


if __name__ == "__main__":
    main()
