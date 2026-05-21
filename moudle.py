class player:
    def __init__(self, client_id, name):
        self.id = client_id
        self.name = name

        self.alive = True
        self.hp = 0
        self.mp = 0
        self.coin = 0
        self.element = "None"
        self.strength = 0
        self.agile = 0
        self.burning = 0
        self.frozen = 0
        self.hand = []

class room:
    def __init__(self, room_number):
        self.room_number = room_number 
        self.players = {}               
        self.status = "LOBBY"           
        self.game_instance = None