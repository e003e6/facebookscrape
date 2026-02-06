from bs4 import BeautifulSoup
import json
import os
import re
from collections import deque


class UniqueStack:
    def __init__(self, maxlen: int):
        self.stack = deque(maxlen=maxlen)
        self.set_items = set()

    def push(self, item: str):
        if item in self.set_items:
            # ha már benne van, eltávolítjuk (hogy újra a tetejére kerüljön)
            self.stack.remove(item)
        elif len(self.stack) == self.stack.maxlen:
            removed = self.stack.popleft()
            self.set_items.remove(removed)

        self.stack.append(item)
        self.set_items.add(item)

    def __contains__(self, item: str) -> bool:
        return item in self.set_items

    def __repr__(self):
        return f"Stack(top -> bottom): {list(reversed(self.stack))}"


def parse_number(s: str):
    s = s.strip().replace("\xa0", " ").replace(",", ".")
    try:
        if s.endswith("E"):
            return int(float(s[:-1].strip()) * 1000)
        return int(float(s))
    except Exception:
        return None


def parse_facebook_stats(text: str):
    # Összes szám kinyerése
    raw_numbers = re.findall(r"[\d.,]+\s*E?", text.replace("\xa0", " "))
    numbers = [parse_number(n) for n in raw_numbers if parse_number(n) is not None]

    if not numbers:
        return {"reakció": None, "hozzászólás": None, "megosztás": None}

    # Duplikált második érték szűrése, ha megegyezik az elsővel
    if len(numbers) >= 2 and numbers[0] == numbers[1]:
        del numbers[1]

    reakcio = numbers[0]
    hozzaszolas = None
    megosztas = None

    # A Facebook UI-ban tipikusan a footerben: [reakció] [hozzászólás] [megosztás]
    if len(numbers) >= 3:
        hozzaszolas = numbers[-2]
        megosztas = numbers[-1]
    elif len(numbers) == 2:
        megosztas = numbers[1]

    return {"reakció": reakcio, "hozzászólás": hozzaszolas, "megosztás": megosztas}


def open_html(path: str):
    with open(path, "r", encoding="utf-8") as f:
        # a snapshotban a beépített html általában jól megy lxml-lel
        return BeautifulSoup(f, "lxml")


def _find_post_root_from_message(msg_tag, max_up: int = 30):
    """
    A feltöltött snapshot struktúrája alapján:
    - a poszt szövege: [data-ad-preview="message"]
    - a szerző blokk: div[data-ad-rendering-role="profile_name"]
    - a poszt footerben gombok: "Tetszik", "Hozzászólás", "Megosztás"
    """
    p = msg_tag
    # szigorú: legyen benne profilnév + legyen benne Tetszik gomb
    for _ in range(max_up):
        if p is None:
            break
        if p.select_one('div[data-ad-rendering-role="profile_name"]') and p.find(
            string=re.compile(r"^Tetszik$")
        ):
            return p
        p = p.parent

    # fallback: legalább profilnév legyen
    p = msg_tag
    for _ in range(max_up):
        if p is None:
            break
        if p.select_one('div[data-ad-rendering-role="profile_name"]'):
            return p
        p = p.parent

    return None


def _extract_stats_text(post_root):
    """
    A snapshotban a számlálók (reakció/komment/megosztás) a footer részben vannak,
    tipikusan úgy, hogy a footer szöveg tartalmazza pl.:
    "Az összes reakció: 3,1 E ... 161 94 Tetszik Hozzászólás Megosztás"
    Innen a parse_facebook_stats már ki tudja szedni az értékeket.
    """
    labels = ["Tetszik", "Hozzászólás", "Megosztás", "Az összes reakció:"]
    label_nodes = []
    for lab in labels:
        # pontos egyezés (pl. Tetszik), illetve "Az összes reakció:" is így szerepel
        if lab.endswith(":"):
            label_nodes.extend(post_root.find_all(string=re.compile(re.escape(lab))))
        else:
            label_nodes.extend(post_root.find_all(string=re.compile(rf"^{re.escape(lab)}$")))

    if not label_nodes:
        return ""

    # vegyük az első találat környékét, majd menjünk felfelé, amíg egy értelmes footer-blokkot kapunk
    node = label_nodes[0].parent
    chosen = None

    for _ in range(12):
        txt = node.get_text(" ", strip=True).replace("\xa0", " ")
        # kell legyen benne legalább egy szám + legalább 2 label, hogy tényleg footer legyen
        label_hits = sum(1 for lab in ["Tetszik", "Hozzászólás", "Megosztás"] if lab in txt)
        if re.search(r"[\d.,]+\s*E", txt) or re.search(r"\b\d+\b", txt):
            if label_hits >= 2:
                chosen = node
                break
        node = node.parent
        if node is None:
            break

    if chosen is None:
        chosen = label_nodes[0].parent

    return chosen.get_text(" ", strip=True).replace("\xa0", " ")


def get_posts_from_html(soup):
    posts = []

    # 1) A poszt-szöveg a snapshotban stabilan ezzel a markerrel jön
    message_nodes = soup.select('[data-ad-preview="message"]')

    for msg in message_nodes:
        post_root = _find_post_root_from_message(msg)
        if post_root is None:
            continue

        # szerző
        pn = post_root.select_one('div[data-ad-rendering-role="profile_name"]')
        if not pn:
            continue
        szerzo = pn.get_text(" ", strip=True)

        # poszt szöveg
        text = msg.get_text(" ", strip=True)
        # "Továbbiak" jellegű csonkolt snapshotok kiszűrése
        if not text or text.endswith("Továbbiak") or text.endswith("Továbbiak…"):
            continue

        # statok
        stats_text = _extract_stats_text(post_root)
        stats = parse_facebook_stats(stats_text)

        posts.append({"szerzo": szerzo, "text": text, **stats})

    return posts


def unique(lista):
    unique_dicts = []
    seen = set()

    for d in lista:
        items_tuple = tuple(sorted(d.items()))
        if items_tuple not in seen:
            seen.add(items_tuple)
            unique_dicts.append(d)
    return unique_dicts


def export_posts_to_json(posts_list, filename):
    jsonobj = {
        "Metadata": {
            "Lementett postok száma": len(posts_list),
            "Kezdeti dátum": "2025.07.08",
            "Befejező dátum": "2024.10.22",
        },
        "Posztok": posts_list,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(jsonobj, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    url = "./facebook/snapshots2"

    lrp = UniqueStack(maxlen=20)  # last read posts
    allposts = []

    for filename in sorted(os.listdir(url)):
        if not filename.endswith(".html"):
            continue

        path = os.path.join(url, filename)
        print(f"Feldolgozás: {filename}")
        print("Összes poszt:", len(allposts))

        soup = open_html(path)
        posts = get_posts_from_html(soup)

        for post in posts:
            if post["text"] in lrp:
                continue
            lrp.push(post["text"])
            allposts.append(post)

    print("Kiolvasott posztok száma:", len(allposts))

    unique_dicts = unique(allposts)
    print("Egyedi posztok száma:", len(unique_dicts))

    export_posts_to_json(unique_dicts, "posztok_exp_2.json")
