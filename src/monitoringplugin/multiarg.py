from typing import Iterator, Optional, Union


class MultiArg(object):
    args: list[str]
    fill: Optional[str]

    def __init__(
        self,
        args: Union[list[str], str],
        fill: Optional[str] = None,
        splitchar: str = ",",
    ):
        if isinstance(args, list):
            self.args = args
        else:
            self.args = args.split(splitchar)
        self.fill = fill

    def __len__(self) -> int:
        return self.args.__len__()

    def __iter__(self) -> Iterator[str]:
        return self.args.__iter__()

    def __getitem__(self, key: int) -> Optional[str]:
        try:
            return self.args.__getitem__(key)
        except IndexError:
            pass
        if self.fill is not None:
            return self.fill
        try:
            return self.args.__getitem__(-1)
        except IndexError:
            return None
