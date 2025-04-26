import aiohttp
from bs4 import BeautifulSoup
import datetime
import re

BASE = "https://recentlybooked.com"

async def getStates(session):
    url = f"{BASE}/Default"
    async with session.get(url) as resp:
        soup = BeautifulSoup(await resp.text(), "lxml")
        row = soup.select_one('div#section-states div.row.hidden-sm.hidden-xs')
        if not row:
            return []
        out = []
        for col in row.select('div.col'):
            for a in col.find_all('a'):
                txt = a.text.strip()
                abbr = a['href'].strip('/').upper()
                m = re.match(r'^(.+?)\s*\((\d+)\)$', txt)
                name, cnt = m.groups() if m else (txt, '0')
                out.append({"abbreviation": abbr, "name": name, "url": BASE + a['href'], "count": int(cnt)})
        return out

async def getCounties(session, state):
    url = f"{BASE}/{state}"
    async with session.get(url) as resp:
        soup = BeautifulSoup(await resp.text(), "lxml")
        panel = soup.select_one('div#ContentPlaceHolder1_pnlCounties div.row.hidden-sm.hidden-xs')
        if not panel:
            panel = soup.select_one('div#ContentPlaceHolder1_pnlCounties div.row')
        if not panel:
            return []
        out = []
        for col in panel.select('div.col'):
            for a in col.find_all('a'):
                txt = a.text.strip()
                m = re.match(r'^(.+?)\s*\((\d+)\)$', txt)
                name, cnt = m.groups() if m else (txt, '0')
                out.append({"name": name, "url": BASE + a['href'], "count": int(cnt)})
        return out

async def searchMugshots(session, state, county=None, charge=None, startDate=None, endDate=None, page=1):
    if not startDate:
        now = datetime.datetime.now()
        startDate = (now - datetime.timedelta(days=60)).strftime('%m/%d/%Y')
        endDate = now.strftime('%m/%d/%Y')
    else:
        now = datetime.datetime.now()
        if not endDate:
            endDate = now.strftime('%m/%d/%Y')
    path = f"/{state}"
    if county:
        path += f"/{county}"
    url = f"{BASE}{path}/?StartDate={startDate}&EndDate={endDate}"
    if charge:
        url += f"&SearchCharge={charge}"
    if page > 1:
        url += f"&Page={page}"
    async with session.get(url) as resp:
        soup = BeautifulSoup(await resp.text(), "lxml")
        grid = soup.select_one('div#portfolio-grid')
        if not grid:
            return []
        out = []
        for card in grid.select("div.pf-item"):
            thumb = card.select_one("div.thumb.img-back")
            style = thumb.get("style", "") if thumb else ""
            if "Blank" in style or not thumb:
                continue
            img = re.search(r'url\([\'"]?(.+?)[\'"]?\)', style)
            mugshotUrl = BASE + img.group(1) if img else ""
            info = card.select_one("div.search-info")
            name = info.select_one(".name").text.strip() if info else ""
            inners = info.find_all("div")
            location = inners[2].text.strip() if len(inners) > 2 else ""
            a = card.select_one("a")
            profileUrl = BASE + a['href'] if a else ""
            out.append({
                "profileUrl": profileUrl,
                "mugshotUrl": mugshotUrl,
                "name": name,
                "location": location,
                "state": state,
                "county": county if county else (location.split(" County")[0] if " County" in location else ""),
            })
        return out

async def getProfile(session, profileUrl, mugshotUrl=""):
    async with session.get(profileUrl) as resp:
        soup = BeautifulSoup(await resp.text(), "lxml")
        info = soup.select_one("div.col-md-7 .info")
        name = info.h2.text.strip() if info and info.h2 else ""
        h1 = info.h1 if info else None
        location, state, county = "", "", ""
        if h1 and h1.select_one("a"):
            location = h1.select_one("a").text.strip()
            sc = h1.select_one("a")['href'].strip("/").split("/")
            if len(sc) >= 2:
                state, county = sc[0].upper(), sc[1]
        cells = info.select(".row > .col-md-12, .row > .col-md-6") if info else []
        bookingNumber = bookingDate = age = gender = race = arrestingAgency = ""
        for c in cells:
            tx = c.text
            if "Booking Number" in tx: bookingNumber = tx.split(":")[-1].strip()
            elif "Booking Date" in tx: bookingDate = tx.split(":")[-1].strip()
            elif "Age:" in tx: age = tx.split(":")[-1].strip()
            elif "Gender:" in tx: gender = tx.split(":")[-1].strip()
            elif "Race:" in tx: race = tx.split(":")[-1].strip()
            elif "Arresting Agency:" in tx: arrestingAgency = tx.split(":")[-1].strip()
        oinfo = soup.select_one("div.opening-info ul")
        charges = []
        if oinfo:
            for li in oinfo.find_all("li"):
                bds = li.find_all("b")
                desc = bond = None
                for b in bds:
                    label = b.text.strip()
                    tx = b.next_sibling.strip() if b.next_sibling else ""
                    if "Charge Description" in label:
                        desc = tx
                    elif "Bond Amount" in label:
                        bond = tx
                charges.append({"desc": desc, "bondAmount": bond})
        if not mugshotUrl:
            imgdiv = soup.select_one(".img-back[style]")
            if imgdiv:
                style = imgdiv['style']
                if "Blank" not in style:
                    m = re.search(r"url\([\'\"]?(.+?)[\'\"]?\)", style)
                    mugshotUrl = BASE + m.group(1) if m else ""
        return {
            "name": name,
            "profileUrl": profileUrl,
            "mugshotUrl": mugshotUrl,
            "county": county,
            "state": state,
            "location": location,
            "bookingNumber": bookingNumber,
            "bookingDate": bookingDate,
            "age": age,
            "gender": gender,
            "race": race,
            "arrestingAgency": arrestingAgency,
            "charges": charges
        }
