import datetime


def to_file_name(name):
    name = name.replace('-', '_')
    name = name.replace(':', '_')
    name = name.replace('.', '_')

    return name


def to_iso_format(date: datetime.datetime) -> str:
    if date.microsecond == 0:
        return '{}.000000'.format(date.isoformat())
    else:
        return date.isoformat()
