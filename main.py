from __future__ import print_function
import os
from time import sleep
import requests, re

timeout = 10


# ***** CONFIG HERE *** #
# backup is a course you're already registered in, but wish to swap out for another
username = "YOUR CWL USERNAME"
password = "YOUR CWL PASSWORD"
needed = [
    Section("CPSC", 213, 101),
    Section("SCAN", 335, "001"),
    Section("CPSC", 221, "L1A"),
    Section("CPSC", 221, 101, backup=Section("CPSC", 221, "1W1")),
    Section("MATH", "200", "102", backup=Section("MATH", 200, "101"))

]
# ********
class Section:
    def __init__(self, dept, course, section, session=None, backup=None):
        self.dept = dept
        self.course = str(course)
        self.section = str(section)
        self.session = session
        self.backup = backup

    def get_url(self):
        return "https://courses.students.ubc.ca/cs/main?pname=subjarea&tname=subjareas&req=5&dept=" + self.dept + "&course=" + self.course + "&section=" + self.section

    def get_register_url(self):
        return "https://courses.students.ubc.ca/cs/main?pname=subjarea&tname=subjareas&submit=Register%20Selected&wldel=" + self.dept + "|" + self.course + "|" + self.section

    def get_drop_url(self):
        return "https://courses.students.ubc.ca/cs/main?pname=subjarea&tname=subjareas&submit=Drop+Selected+Section&wldel=" + self.dept + "|" + self.course + "|" + self.section

    def drop(self, ses=None):
        if ses is not None:
            self.session = ses
        if self.session is None:
            raise Exception("No Session")
        self.session.get(self.get_url(), timeout=timeout)
        r = self.session.get(self.get_drop_url(), headers={'referer': self.get_url()}, timeout=timeout)
        if "The section was dropped successfully." not in r.text:
            pass

    def replace_backup(self):
        self.backup.drop(ses=self.session)
        self.backup = None
        return self.register()

    def register(self, ses=None):
        if ses is not None:
            self.session = ses
        if self.session is None:
            raise Exception("No Session")
        self.session.get(self.get_url(), timeout=timeout)
        r = self.session.get(self.get_register_url(), headers={'referer': self.get_url()}, timeout=timeout)
        status = []
        if "This section is either full" in r.text:
            status.append("full")

        if "The section was added successfully." in r.text:
            status.append("success")
            if self.backup is not None:
                print("dropping backup")
                self.backup.drop(ses=self.session)

        if "You are already registered in this section" in r.text:
            status.append("already registered")
        if "You are already registered in another section of this course." in r.text:
            if self.backup is not None and "full" not in status:
                print("looks good, drop backup => ", end="")
                return self.replace_backup()
            else:
                status.append("another" + (" (but has backup)" if self.backup is not None else ""))
        if "Add was Unsuccessful" in r.text:
            status.append("fail")
        if "The requested section is either no longer offered at" in r.text:
            status.append("nonexistent")
        if len(status) < 1:
            pass
        return status, r

    def __str__(self):
        return self.dept + "|" + self.course + "|" + self.section + ("*" if self.backup is not None else "")


def is_logged_in(session):
    url = "https://cas.id.ubc.ca/ubc-cas/login"
    r = session.get(url)
    return "You have successfully logged into UBC CAS." in r.text


def login(user, pw, session):
    url = "https://cas.id.ubc.ca/ubc-cas/login"
    login_page = session.get(url)
    if "You have successfully logged into UBC CAS." in login_page.text:
        return
    lt = re.search('<input.*?name="lt".*?value="(.*?)".*?/>', login_page.content.decode("ascii", "ignore")).group(
        1)
    execution = re.search('<input.*?name="execution".*?value="(.*?)".*?/>',
                          login_page.content.decode("ascii", "ignore")).group(
        1)
    userIP = re.search('<input.*?name="User".*?value="(.*?)".*?/>', login_page.content.decode("ascii", "ignore")).group(
        1)
    server = re.search('<input.*?name="Server".*?value="(.*?)".*?/>',
                       login_page.content.decode("ascii", "ignore")).group(
        1)
    jsessionid = session.cookies['JSESSIONID']
    r = session.post(url + ";jsessionid=" + jsessionid,
                     data={
                         "username": user,
                         "password": pw,
                         "lt": lt,
                         "execution": execution,
                         "_eventId": "submit",
                         "submit": "Continue+%3E",
                         "IdP+Service": "cas.id.ubc.ca",
                         "User": userIP,
                         "Server": server

                     }, timeout=timeout)
    if not r.ok:
        raise RuntimeError(r.reason)
    if not "You have successfully logged into UBC CAS." in r.text:
        raise RuntimeError("invalid login")


ses = requests.Session()

assert not is_logged_in(ses)

done = []
successes = []
needsLogin = True
while True:
    try:
        if needsLogin:
            ses = requests.Session()
            print("logging in")
            login(username,password, ses)
            assert is_logged_in(ses)
            ses.get("https://courses.students.ubc.ca/cs/secure/login", timeout=timeout)
            print("logged in")
            needsLogin = False
        os.system(['clear', 'cls'][os.name == 'nt'])  # clear
        print("Need to get into " + ', '.join([str(crs) for crs in needed]))
        if len(successes) > 0:
            print("Successes: " + ', '.join([str(crs) for crs in successes]))
        for crs in needed:
            print("trying " + str(crs), end='...')
            s, r = crs.register(ses=ses)
            s = ', '.join([str(x) for x in s])
            print(s.upper())
            if "already" in s:
                done.append(crs)
            if "success" in s:
                done.append(crs)
                successes.append(crs)

            if 'value="Logout"' not in r.text and "value='Logout'" not in r.text:
                print("needs a fresh login...")
                needsLogin = True
                break



        for crs in done:
            needed.remove(crs)
    except requests.Timeout:
            print("TIMED OUT")
    except Exception as e:
            print(e)
            continue
    done = []
    sleep(5)
