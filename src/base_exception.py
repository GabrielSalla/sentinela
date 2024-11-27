class BaseSentinelaException(Exception):
    def __str__(self) -> str:
        return self.__class__.__name__ + ": " + str(self.args[0])
