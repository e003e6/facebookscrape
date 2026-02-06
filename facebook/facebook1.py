from playwright.sync_api import sync_playwright
import time
import os
import random

EXPORT_DIR = "snapshots_ov"
os.makedirs(EXPORT_DIR, exist_ok=True)

snapshot_index = 0

def run(proxy=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, proxy=proxy)

        context = browser.new_context()
        page = context.new_page()
        page.goto("https://facebook.com")

        page.evaluate("document.body.style.zoom = '80%'")

        input(">>> Jelentkezz be, menj a céloldalra, majd nyomj ENTER-t...")
        page.evaluate("document.body.style.zoom = '80%'")

        print(">>> Feldolgozás elkezdődött.")

        process_posts(page)

        browser.close()


def process_posts(page):
    nincs_uj = 0

    while True:
        # manuális megszakítás lehetősége fájllal
        if os.path.exists("stop.txt"):
            print("[info] stop.txt észlelve, leállás.")
            break

        # megnézem hogy tiltott-e a facebook
        if "facebook.com/friends" in page.url:
            print("[warn] Átirányítás történt a friends oldalra!")
            #time.sleep(8)
            # vissza gomb
            break

        # lenyitom az összes továbbiak gombot
        open_all_read_more_buttons(page)

        # lejebb görgetek és megvizsgálom hogy változott e a DOM
        is_page_new = scroll_down(page)

        if is_page_new == 1:
            print("[info] A DOM mérte nőtt.")

        elif is_page_new == 0:
            print("[info] Nem változott a DOM.")
            if nincs_uj < 5:
                nincs_uj += 1
                continue
            else:
                print(f'[info] {nincs_uj} alkalommal nem változott a DOM. Leállás.')
                break

        elif is_page_new == -1:
            print("[info] A DOM mérete csökkent.")

        nincs_uj = 0

    # ha kilépek a ciklusból akkor leállítom
    if os.path.exists("stop.txt"):
        os.remove("stop.txt")


def open_all_read_more_buttons(page):
    global snapshot_index

    seen = set()

    while True:

        # lekérem az összes gombot a dom-ban ami visible
        btns = [b for b in page.query_selector_all('div[role="button"][tabindex="0"]:not([aria-haspopup]):not([data-opened]):has-text("Továbbiak")')
                if b.is_visible()]

        if not btns:
            print('Nincsen több gomb a DOM-ban -- return')
            return

        print('Talált gombok száma: ', len(btns))

        for i in range(len(btns)):
            btn = btns[i]
            parent_text = btn.evaluate_handle("el => el.parentNode").inner_text()

            print('gomb:', btn)
            print('gomb text:', btn.inner_text().strip())
            print('szulo text:', parent_text)

            if parent_text in seen:
                continue
            else:
                break

        else: # for else, ha véget ér a cikus kilépés nélkül
            print('A DOM-ban lévő összes gombot próbálta már lenyitni, de van amit nem lehetet -- return')
            return

        # kiválasztottam a következő gombot, amit még nem próbáltam megnyomni

        try:
            box = btn.bounding_box()
            if not box:
                print("[warn] Gomb már nincs a DOM-ban (bounding_box None) -- gomb kizárva a feldolhozásból")
                seen.add(parent_text)
                continue

            scroll_to_button(btn, page)

            if not btn.is_visible():
                print("[warn] Gomb a scroll után nem látható -- gomb kizárva a feldolhozásból")
                seen.add(parent_text)
                continue

            btn.click(force=True)
            print("poszt lenyitva")
            btn.evaluate("el => el.setAttribute('data-opened', '1')")
            seen.add(parent_text)
            # mentem a html-t
            save_full_html(page.content())

            time.sleep(random.uniform(4.0, 6.0))

        except Exception as e:
            print(f"[warn] Gomb kattintás hiba: {e}")
            try:
                btn.evaluate("el => el.setAttribute('data-opened', '1')")
            except:
                pass
            seen.add(parent_text)
            continue



def scroll_down(page):
    '''
    Lefelé görget az oldalon.
    A DOM teljes magasságát (scrollHeight) figyeli. Összehasonlítja a görgetés előtti és utáni állapotot.
    '''

    print('görgetés...', sep='')
    old_height = page.evaluate("() => document.body.scrollHeight")

    page.mouse.wheel(0, random.randint(1200, 1800))

    time.sleep(random.uniform(3.0, 8.0))

    print('...görgetés vége')

    new_height = page.evaluate("() => document.body.scrollHeight")

    if new_height > old_height:
        return 1
    elif new_height < old_height:
        return -1
    else:
        return 0


def save_full_html(html):
    global snapshot_index

    with open(f"{EXPORT_DIR}/page_snapshot_{snapshot_index:04d}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[debug] Oldal HTML mentve: page_snapshot_{snapshot_index:04d}.html")

    snapshot_index += 1


def scroll_to_button(btn, page):
    box = btn.bounding_box()
    if not box:
        return

    current_scroll = page.evaluate("() => window.scrollY")
    target_y = box['y'] - random.randint(100, 300)

    # Ne görgessünk visszafelé
    if target_y < current_scroll:
        print("[debug] Gomb túl magasan, nem görgetünk vissza.")
        return

    distance = target_y - current_scroll
    step_size = random.randint(150, 350)
    steps = int(abs(distance) / step_size) + 1

    for _ in range(steps):
        delta = random.randint(100, 400)
        page.mouse.wheel(0, delta)
        time.sleep(random.uniform(0.15, 0.4))




if __name__ == "__main__":

    #proxy = {"server": "http://77.242.144.117:47126", "username": "5nRy0BROt9Rgq86", "password": "I7KkTN87BS6wHKl"}

    run()


