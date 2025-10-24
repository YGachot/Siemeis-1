import os
import random
import string
import time
from ..player import Game, SimeisError
import sys

def generate_random_username(length=70):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class TestGame:
    def setUp(self, username):
        for _ in range(10):
            self.username = username
            try:
                self.game = Game(self.username)
                break
            except SimeisError as e:
                if "already exists" in str(e).lower():
                    continue
                else:
                    raise e
        else:
            raise Exception("Impossible de créer un joueur unique après plusieurs tentatives.")

        self.game.init_game()
        self.initial_status = self.game.get(f"/player/{self.game.pid}")
        self.initial_money = self.initial_status["money"]
        self.station_id = list(self.initial_status["stations"].keys())[0]

    def test_buy_ship_and_module(self):
        ships = self.initial_status["ships"]
        assert len(ships) == 1, "Le joueur devrait avoir un seul vaisseau"
        assert len(ships[0]["modules"]) == 0, "Le vaisseau ne devrait pas avoir de module au départ"

        self.game.buyMiningModule("Miner", ships[0])
        status_after_module = self.game.get(f"/player/{self.game.pid}")
        money_after_module = status_after_module["money"]

        assert money_after_module < self.initial_money, "L'argent n'a pas diminué après l'achat du module"

        ship = status_after_module['ships'][0]
        assert len(ship["modules"]) == 1, "Le module n'a pas été correctement ajouté"

        print("[✓] test_buy_ship_and_module réussi")

    def voyage(self):
        shipAvant = self.game.get(f"/player/{self.game.pid}")["ships"][0]
        assert shipAvant['state'] == 'Idle', "Vous n'êtes pas à l'arrêt"

        if(self.game.goPlanet(shipAvant)):
            time.sleep(0.5)
            ship = self.game.infoVaisseaux(shipAvant['id'])[0]

            assert list(ship["state"].keys())[0] == 'InFlight', "Vous n'êtes pas en vol"
            
        else:
            ship = self.game.infoVaisseaux(shipAvant['id'])[0]
            assert ship['state'] == 'Idle', "Vous êtes parti au minage"
        print("[✓] voyage réussi")


    def testAction(self):
        shipAvant = self.game.get(f"/player/{self.game.pid}")["ships"][0]
        assert shipAvant['state'] == 'Idle', "Votre initialisation à un problème"
        station = self.game.get(f"/station/{self.game.sta}")
        x,y,z = station['position']
        self.game.travel(shipAvant['id'],[x + 100, y + 100, z + 100])
        time.sleep(0.5)
        ship = self.game.get(f"/player/{self.game.pid}")["ships"][0]
        assert list(ship["state"].keys())[0] == 'InFlight', "Votre navire ne bouge pas"
        time.sleep(3.5)
        assert shipAvant['state'] == 'Idle', "Vous n'êtes pas à l'arrêt"

        print("[✓] testAction réussi")


def tearDown(name):
    print("[*] Test terminé pour l'utilisateur", name)
    fichier = f"{name}.json"
    if os.path.exists(fichier):
        os.remove(fichier)
        print(f"[*] Fichier {fichier} supprimé.")
    else:
        print(f"[!] Le fichier {fichier} n'existe pas.")

def scenario1():
    print("\n--- Scénario 1 : Achat de module ---")
    success, fail = 0, 0
    for i in range(10):
        username = generate_random_username()
        try:
            test = TestGame()
            test.setUp(username)
            test.test_buy_ship_and_module()
            success += 1
        except Exception as e:
            print(f"[✗] Échec du test {i+1} : {e}")
            fail += 1
        tearDown(username)
    print(f"Fin du scénario 1 : {success} réussis, {fail} échoués\n")
    return success, fail

def scenario2():
    print("\n--- Scénario 2 : Achat de module voyage dans l'espace puis retour ---")
    success, fail = 0, 0
    for i in range(10):
        username = generate_random_username()
        try:
            test = TestGame()
            test.setUp(username)
            test.test_buy_ship_and_module()
            test.voyage()
            success += 1
        except Exception as e:
            print(f"[✗] Échec du test {i+1} : {e}")
            fail += 1
        tearDown(username)
    print(f"Fin du scénario 2 : {success} réussis, {fail} échoués\n")
    return success, fail

def scenario3():
    print("\n--- Scénario 3 : Réparation fictive ---")
    success, fail = 0, 0
    for i in range(10):
        username = generate_random_username()
        try:
            test = TestGame()
            test.setUp(username)
            test.test_buy_ship_and_module()
            test.testAction()
            success += 1
        except Exception as e:
            print(f"[✗] Échec du test {i+1} : {e}")
            fail += 1
        tearDown(username)
    print(f"Fin du scénario 3 : {success} réussis, {fail} échoués\n")
    return success, fail



if __name__ == "__main__":
    total_success, total_fail = 0, 0

    for scenario in [scenario1, scenario2, scenario3]:
        s, f = scenario()
        if f == 0:
            total_success+=1
        else:
            total_fail+=1

    print("=== Résumé final ===")
    print(f"✅ Tests réussis : {total_success}")
    print(f"❌ Tests échoués : {total_fail}")
    print("====================")
    if total_fail > 0:
        sys.exit(1)
