from .u import helper

class App:
    def run(self, x):
        return helper(x) + 1

def main():
    return App().run(3)
