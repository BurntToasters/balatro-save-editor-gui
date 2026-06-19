from .save_file import BalatroSaveFile


class BalatroSaveEditor(object):
    def __init__(self, save_file_path):
        self.balatro_save_file = BalatroSaveFile(save_file_path)

    def edit_money(self, new_value):
        # Set dollars
        self.balatro_save_file['GAME']['dollars'] = str(new_value)

    def edit_chips(self):
        # Set current chips to just under the blind target
        try:
            target = int(self.balatro_save_file['BLIND']['chips'].structs[0])
        except ValueError:
            target = int(float(self.balatro_save_file['BLIND']['chips'].structs[0]))
        self.balatro_save_file['GAME']['chips'] = str(target - 1)
        self.balatro_save_file['GAME']['chips_text'] = f'{target - 1:,}'

    def edit_multipliers(self, new_mult=10000):
        # Set mult for every hand type
        for hand in self.balatro_save_file['GAME']['hands']:
            hand['mult'] = str(new_mult)

    def edit_card_limits(self, joker_limit=20, consumable_limit=10):
        self.balatro_save_file['cardAreas']['jokers']['config']['card_limit'] = str(joker_limit)
        self.balatro_save_file['cardAreas']['jokers']['config']['temp_limit'] = str(joker_limit)
        self.balatro_save_file['cardAreas']['consumeables']['config']['card_limit'] = str(consumable_limit)
        self.balatro_save_file['cardAreas']['consumeables']['config']['temp_limit'] = str(consumable_limit)

    def edit_card_abilities(self):
        # Strip 'eternal' from all jokers
        for joker in self.balatro_save_file['cardAreas']['jokers']['cards']:
            if 'eternal' in joker['ability']:
                joker['ability']['eternal'] = 'false'
