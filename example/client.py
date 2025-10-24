PORT=8081
URL=f"http://127.0.0.1:{PORT}"
#URL=f"http://103.45.247.164:{PORT}"

import os
import sys
import math
import time
import json
import string
import urllib.request
import threading

class SimeisError(Exception):
    pass

# Théorème de Pythagore pour récupérer la distance entre 2 points dans l'espace 3D
def get_dist(a, b):
    return math.sqrt(((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2) + ((a[2] - b[2]) ** 2))

# Check if types are present in the list
def check_has(alld, key, *req):
    alltypes = [c[key] for c in alld.values()]
    return all([k in alltypes for k in req])

class Game:
    def __init__(self, username):
        # Init connection & setup player
        assert self.get("/ping")["ping"] == "pong"
        print("[*] Connection to server OK")
        self.setup_player(username)
        self.username = username
        # Useful for our game loops
        self.pid = self.player["playerId"] # ID of our player
        self.sid = None    # ID of our ship
        self.sta = None    # ID of our station

    def get(self, path, **qry):
        if hasattr(self, "player"):
            qry["key"] = self.player["key"]

        tail = ""
        if len(qry) > 0:
            tail += "?"
            tail += "&".join([
                "{}={}".format(k, urllib.parse.quote(v)) for k, v in qry.items()
            ])

        qry = f"{URL}{path}{tail}"
        reply = urllib.request.urlopen(qry, timeout=1)

        data = json.loads(reply.read().decode())
        err = data.pop("error")
        if err != "ok":
            raise SimeisError(err)

        return data

    def disp_status(self):
        status = self.get("/player/" + str(self.pid))
        print("[*] Current status: {} credits, costs: {}, time left before lost: {} secs".format(
            round(status["money"], 2), round(status["costs"], 2), int(status["money"] / status["costs"]),
        ))

    # If we have a file containing the player ID and key, use it
    # If not, let's create a new player
    # If the player has lost, print an error message
    def setup_player(self, username, force_register=False):
        # Sanitize the username, remove any symbols
        username = "".join([c for c in username if c in string.ascii_letters + string.digits]).lower()

        # If we don't have any existing account
        if force_register or not os.path.isfile(f"./{username}.json"):
            player = self.get(f"/player/new/{username}")
            with open(f"./{username}.json", "w") as f:
                json.dump(player, f, indent=2)       
            print(f"[*] Created player {username}")
            self.player = player

        # If an account already exists
        else:
            with open(f"./{username}.json", "r") as f:
                self.player = json.load(f)
            print(f"[*] Loaded data for player {username}")

        # Try to get the profile
        try:
            player = self.get("/player/{}".format(self.player["playerId"]))

        # If we fail, that must be that the player doesn't exist on the server
        except SimeisError:
            # And so we retry but forcing to register a new account
            return self.setup_player(username, force_register=True)

        # If the player already failed, we must reset the server
        # Or recreate an account with a new nickname
        if player["money"] <= 0.0:
            print("!!! Player already lost, please restart the server to reset the game")
            sys.exit(0)

    def buy_first_ship(self, sta):
        # Get all the ships available for purchasing in the station
        available = self.get(f"/station/{sta}/shipyard/list")["ships"]
        # Get the cheapest option
        cheapest = sorted(available, key = lambda ship: ship["price"])[0]
        print("[*] Purchasing the first ship for {} credits".format(cheapest["price"]))
        # Buy it
        self.get(f"/station/{sta}/shipyard/buy/" + str(cheapest["id"]))

    def buy_first_mining_module(self, modtype, sta, sid):
        # Buy the mining module
        all = self.get(f"/station/{sta}/shop/modules")
        mod_id = self.get(f"/station/{sta}/shop/modules/{sid}/buy/{modtype}")["id"]

        # Check if we have the crew assigned on this module
        # If not, hire an operator, and assign it to the mining module of our ship
        ship = self.get(f"/ship/{sid}")
        if not check_has(ship["crew"], "member_type", "Operator"):
            op = self.get(f"/station/{sta}/crew/hire/operator")["id"]
            self.get(f"/station/{sta}/crew/assign/{op}/{sid}/{mod_id}")

    def hire_pilot(self, sta, ship):
        # Hire a pilot, and assign it to our ship
        pilot = self.get(f"/station/{sta}/crew/hire/pilot")["id"]
        self.get(f"/station/{sta}/crew/assign/{pilot}/{ship}/pilot")

    def hire_trader(self, sta):
        # Hire a trader, assign it on our station
        trader = self.get(f"/station/{sta}/crew/hire/trader")["id"]
        self.get(f"/station/{sta}/crew/assign/{trader}/trading")

    def travel(self, sid, pos):
        costs = self.get(f"/ship/{sid}/navigate/{pos[0]}/{pos[1]}/{pos[2]}")
        print("[*] Traveling to {}, will take {}".format(pos, costs["duration"]))
        self.wait_idle(sid, ts=costs["duration"])

    def wait_idle(self, sid, ts=2):
        ship = self.get(f"/ship/{sid}")
        while ship["state"] != "Idle":
            time.sleep(ts)
            ship = self.get(f"/ship/{sid}")

    # Repair the ship:     Buy the plates, then ask for reparation
    def ship_repair(self, sid):
        ship = self.get(f"/ship/{sid}")
        req = int(ship["hull_decay"])

        # No need for any reparation
        if req == 0:
            print("req 0")
            return

        # In case we don't have enough hull plates in stock
        station = self.get(f"/station/{self.sta}")["cargo"]
        if "HullPlate" not in station["resources"]:
            station["resources"]["HullPlate"] = 0

        if station["resources"]["HullPlate"] < req:
            need = req - station["resources"]["HullPlate"]
            print(need)
            bought = self.get(f"/market/{self.sta}/buy/hullplate/{need}")
            print(f"[*] Bought {need} of hull plates for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["HullPlate"] > 0:
            # Use the plates in stock to repair the ship
            repair = self.get(f"/station/{self.sta}/repair/{self.sid}")
            print("[*] Repaired {} hull plates on the ship".format(repair["added-hull"]))

    # Refuel the ship:    Buy the fuel, then ask for a refill
    def ship_refuel(self, sid):
        ship = self.get(f"/ship/{sid}")
        req = int(ship["fuel_tank_capacity"] - ship["fuel_tank"])

        # No need for any refuel
        if req == 0:
            return

        # In case we don't have enough fuel in stock
        station = self.get(f"/station/{self.sta}")["cargo"]
        if "Fuel" not in station["resources"]:
            station["resources"]["Fuel"] = 0
        if station["resources"]["Fuel"] < req:
            need = req - station["resources"]["Fuel"]
            bought = self.get(f"/market/{self.sta}/buy/Fuel/{need}")
            print(f"[*] Bought {need} of fuel for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["Fuel"] > 0:
            # Use the fuel in stock to refill the ship
            refuel = self.get(f"/station/{self.sta}/refuel/{self.sid}")
            print("[*] Refilled {} fuel on the ship for {} credits".format(
                refuel["added-fuel"],
                bought["removed_money"],
            ))

    # Initializes the game:
    #     - Ensure our player exists
    #     - Ensure our station has a Trader hired
    #     - Ensure we own a ship
    #     - Setup the ship
    #         - Hire a pilot & assign it to our ship
    #         - Buy a mining module to be able to farm
    #         - Hire an operator & assign it on the mining module of our ship
    def init_game(self):
        # Ensure we own a ship, buy one if we don't
        status = self.get(f"/player/{self.pid}")
        self.sta = list(status["stations"].keys())[0]
        station = self.get(f"/station/{self.sta}")

        if not check_has(station["crew"], "member_type", "Trader"):
            self.hire_trader(self.sta)
            print("[*] Hired a trader, assigned it on station", self.sta)

        if len(status["ships"]) == 0:
            self.buy_first_ship(self.sta)
            status = self.get(f"/player/{self.pid}") # Update our status
        ship = status["ships"][0]
        self.sid = ship["id"]

        # Ensure our ship has a crew, hire one if we don't
        if not check_has(ship["crew"], "member_type", "Pilot"):
            self.hire_pilot(self.sta, self.sid)
            print("[*] Hired a pilot, assigned it on ship", self.sid)

        print("[*] Game initialisation finished successfully")

    # - Find the nearest planet we can mine
    # - Go there
    # - Fill our cargo with resources
    # - Once the cargo is full, we stop mining, and this function returns
    def go_mine(self):
        print("[*] Starting the Mining operation")
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")

        # Scan the galaxy sector, detect which planet is the nearest
        station = self.get(f"/station/{self.sta}")
        planets = self.get(f"/station/{self.sta}/scan")["planets"]
        nearest = sorted(planets,
            key=lambda pla: get_dist(station["position"], pla["position"])
        )[0]

        # If the planet is solid, we need a Miner to mine it
        # If it's gaseous, we need a GasSucker to mine it
        if nearest["solid"]:
            modtype = "Miner"
        else:
            modtype = "GasSucker"

        #print("[*] Cout par seconde")
        #print(self.costPerSecond())
        #print(self.moneyPlayer())
        #print(self.lifeTime())
        
        # Ensure the ship has a corresponding module, buy one if we don't
        ship = self.get(f"/ship/{self.sid}")
        if not check_has(ship["modules"], "modtype", modtype):
            self.buy_first_mining_module(modtype, self.sta, self.sid)
        print("[*] Targeting planet at", nearest["position"])

        self.wait_idle(self.sid) # If we are currently occupied, wait

        # If we are not current at the position of the target planet, travel there
        if ship["position"] != nearest["position"]:
            self.travel(ship["id"], nearest["position"])

        # Now that we are there, let's start mining
        info = self.get(f"/ship/{self.sid}/extraction/start")
        print("[*] Starting extraction:")
        for res, amnt in info.items():
            print(f"\t- Extraction of {res}: {amnt}/sec")

        # Wait until the cargo is full
        self.wait_idle(self.sid) # The ship will have the state "Idle" once the cargo is full
        print("[*] The cargo is full, stopping mining process")

    # - Go back to the station
    # - Unload all the cargo
    # - Sell it on the market
    # - Refuel & repair the ship

    def scan(self):
        print("[*] Scan operations")

        station = self.get(f"/station/{self.sta}")

        print(station)
        print(self.coutTrajet(12221239808692135915, station))


    def costPerSecond(self):
        return self.get(f"/player/{self.pid}")["costs"]
    
    def moneyPlayer(self):
        return self.get(f"/player/{self.pid}")["money"]
    
    def lifeTime(self):
        player =  self.get(f"/player/{self.pid}")
        return player["money"] / player["costs"]
    
    def getPriceVaisseaux(self):
        return self.get(f"/station/{self.sta}/shipyard/list")

    def infoVaisseaux(self, idVaisseaux):
        vaisseaux = self.get(f"/player/{self.pid}")["ships"]
        return list(filter(lambda id: id['id'] == idVaisseaux, vaisseaux))

    def trajet(self, idVaisseaux, destination=None):
        if destination == None:
            destination = self.get(f"station/{self.sta}/")
        x,y,z = destination["position"]

        return self.get(f"/ship/{idVaisseaux}/travelcost/{x}/{y}/{z}")
    
    def coutTrajet(self, idVaisseaux, destination=None):
        return self.trajet(idVaisseaux, destination)["duration"]
    
    def moduleList(self):
        return self.get(f"/station/{self.sta}/shop/modules")
    
    def upgradeList(self, idVaisseaux):
        try:
            return self.get(f"/station/{self.sta}/shop/modules/{idVaisseaux}/upgrade")
        except SimeisError:
            print("Ships isn't docked")

    def upgradeVaisseauList(self):
        return self.get(f"/station/{self.sta}/shipyard/upgrade")
    
    def __str__(self):
        dataUser = self.getUserInfo()
        dataShips = self.getShipsInfo()
        return dataUser + dataShips
    
    def getUserInfo(self):
        return(f"\nAffichage Joueur : Player id : {self.pid} \ Player name : {self.username} \n\nBalance : {int(self.moneyPlayer())}\nCoût par seconde : {round(self.costPerSecond(), 2)} \nTemps de vie restant : {int(self.lifeTime())} secondes\n")

    def getShipsInfo(self):
        ships = list(self.get(f"/player/{self.pid}")["ships"])
        return f"Nombre de vaisseaux : {len(ships)}, {ships}"

    def go_sell(self):
        self.wait_idle(self.sid) # If we are currently occupied, wait
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")
        status = game.get("/player/" + str(game.pid))

        # If we aren't at the station, got there
        if ship["position"] != station["position"]:
            self.travel(ship["id"], station["position"])

        # Unload the cargo and sell it directly on the market
        for res, amnt in ship["cargo"]["resources"].items():
            if amnt == 0.0:
                continue

            unloaded = self.get(f"/ship/{self.sid}/unload/{res}/{amnt}")
            sold = self.get(f"/market/{self.sta}/sell/{res}/{amnt}")

            print("[*] Unloaded and sold {} of {}, for {} credits".format(
                unloaded["unloaded"], res, sold["added_money"]
            ))



            # if (status["money"] / status["costs"] < 500) :
            #     sold = self.get(f"/market/{self.sta}/sell/{res}/{amnt}")
            #     print("[*] Sold {} of {} for {} credits".format(
            #         unloaded["unloaded"], res, sold["added_money"]
            #     ))

            


        self.ship_repair(self.sid)
        self.ship_refuel(self.sid)

    def view_trader_prices(self):
                
        resources = self.get("/resources")
        market_prices = self.get("/market/prices")["prices"]

        print("[*] Minerais avec taux > 110% :")
        found_high = False
        for mineral, current_price in market_prices.items():
            if mineral in resources:
                base_price = resources[mineral]["base-price"]
                if base_price > 0:
                    percent = (current_price / base_price) * 100
                    if percent > 110.0:
                        print(f"{mineral}: {percent:.2f}%")
                        found_high = True
        if not found_high:
            print("Aucun minerai > 110%")

        print("[*] Minerais avec taux < 90% :")
        found_low = False
        for mineral, current_price in market_prices.items():
            if mineral in resources:
                base_price = resources[mineral]["base-price"]
                if base_price > 0:
                    percent = (current_price / base_price) * 100
                    if percent < 90.0:
                        print(f"{mineral}: {percent:.2f}%")
                        found_low = True
        if not found_low:
            print("Aucun minerai < 90%")

    def buy_module_upgrade(self):
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")

        if (ship["position"] == station["position"]):

            print("[*] Verification de la possibilité d'achat d'une upgrade de module")
            status = game.get("/player/" + str(game.pid))
            print("[*] Money : {} , Temps avant defaite: {}".format(
                round(status["money"], 2), int(status["money"] / status["costs"])
            ))

            listUpgrade = self.get(f"/station/{self.sta}/shop/modules/{self.sid}/upgrade")
            for module_id, module_info in listUpgrade.items():
                if (module_info['price'] < status['money'] and (int((status["money"] - module_info['price']) / status["costs"]) > 500)):
                    upgrade = self.get(f"/station/{self.sta}/shop/modules/{self.sid}/upgrade/1")
                    print("[*] Fonds suffisants, module {} upgrade".format(
                        module_info['module-type']
                    ))
                else:
                    print ("[*] Fonds insuffisants")

    
    def buy_ship_upgrade(self):
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")

        if (ship["position"] == station["position"]):
            print("[*] Verification de la possibilité d'achat d'une upgrade vaisseau")
            listInterestedUpgrade = ['ReactorUpgrade', 'CargoExpansion'] # HullUpgrade
            listUpgrade = self.get(f"/station/{self.sta}/shipyard/upgrade")

            for upgrade in listInterestedUpgrade:
                tryUpgrade = listUpgrade[upgrade]
                status = game.get("/player/" + str(game.pid))

                if (tryUpgrade['price'] < status['money'] and (int((status["money"] - tryUpgrade['price']) / status["costs"]) > 500)):

                    buyUpgrade = self.get(f"/station/{self.sta}/shipyard/upgrade/{self.sid}/{upgrade}")
                    print("[*] Fonds suffisants, {} upgrade".format(
                        upgrade
                    ))
                else:
                    print ("[*] Fonds insuffisants pour {}".format(
                        upgrade
                    ))

    def buy_human_upgrade(self):
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")

        if (ship["position"] == station["position"]):
            print("[*] Verification de la possibilité d'achat d'une upgrade equipage")
            upgradeListEquipage = self.get(f"/station/{self.sta}/crew/upgrade/ship/{self.sid}")
            operator_id = None
            for crew_id, info in upgradeListEquipage.items():
                if info["member-type"] == "Operator":
                    operator_id = crew_id
                    operator_price = info["price"]
                    
                    status = game.get("/player/" + str(game.pid))
                    if operator_price < status["money"] and int((status["money"] - operator_price) / status["costs"]) > 500:
                        upgradeEquipage = self.get(f"/station/{self.sta}/crew/upgrade/ship/{self.sid}/{operator_id}")
                        print("[*] Operator upgrade")
                    else:
                        print("[*] Fonds insuffisants pour upgrader l'operator")

if __name__ == "__main__":
    name = sys.argv[1]
    game = Game(name)
    game.init_game()

    stop_threads = threading.Event()

    def view_prices():
        while not stop_threads.is_set():
            try:
                print("\n[PRICES TRADER] Vérification des prix...")
                game.view_trader_prices()
                time.sleep(5)
            except Exception as e:
                print(f"[PRICES TRADER] Erreur: {e}")
                time.sleep(5)

    def main():
        while not stop_threads.is_set():
            try:
                game.disp_status()
                game.buy_module_upgrade()
                game.buy_ship_upgrade()
                game.buy_human_upgrade()
                game.go_mine()
                game.go_sell()
            except Exception as e:
                print(f"[MAIN] Erreur: {e}")
                time.sleep(5)

    price_thread = threading.Thread(target=view_prices, daemon=True, name="PriceMonitor")
    main_thread = threading.Thread(target=main, daemon=True, name="MainOperations")

    price_thread.start()
    main_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Arrêt...")
        stop_threads.set()
        price_thread.join(timeout=5)
        main_thread.join(timeout=5)