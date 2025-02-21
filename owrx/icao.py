# Various reverse-engineered versions of the allocation algorithms
# used by different countries to allocate 24-bit ICAO addresses based
# on the aircraft registration.
#
# These were worked out by looking at the allocation patterns and
# working backwards to an algorithm that generates that pattern,
# spot-checking aircraft to see if it worked.
# YMMV.
class IcaoRegistration(object):

    @staticmethod
    def find(icao: int):
        result = IcaoRegistration.n_reg(icao)
        if result is not None:
            return result
        result = IcaoRegistration.ja_reg(icao)
        if result is not None:
            return result
        result = IcaoRegistration.hl_reg(icao)
        if result is not None:
            return result
        result = NumericMapping.find(icao)
        if result is not None:
            return result
        result = StrideMapping.find(icao)
        if result is not None:
            return result
        return None;

    # South Korea (HLxxxx)
    @staticmethod
    def hl_reg(icao: int):
        if 0x71BA00 <= icao <= 0x71BF99:
            return "HL" + hex(icao - 0x71BA00 + 0x7200)[2:]
        if 0x71C000 <= icao <= 0x71C099:
            return "HL" + hex(icao - 0x71C000 + 0x8000)[2:]
        if 0x71C200 <= icao <= 0x71C299:
            return "HL" + hex(icao - 0x71C200 + 0x8200)[2:]
        return None

    # Japan (JAxxxx)
    @staticmethod
    def ja_reg(icao: int):
        result = "JA"
        offset = icao - 0x840000
        if icao < 0 or icao >= 229840:
            return None

        # First is a digit
        x = int(offset / 22984)
        if x < 0 or x > 9:
            return None
        result += str(x)
        offset %= 22984

        # Second is a digit
        x = int(offset / 916)
        if x < 0 or x > 9:
            return None
        result += str(x)
        offset %= 916

        # Third and fourth are letters
        if offset >= 340:
            offset -= 340;
            x = int(offset / 24)
            return result + LIMITED_ALPHABET[x] + LIMITED_ALPHABET[offset % 24]

        # Third is a digit, Fourth is a digit or a letter
        x = int(offset / 34)
        result += str(x);
        offset %= 34
        if offset < 10:
            # Fourth is a digit
            return result + str(offset)
        else:
            # Fourth is a letter
            return result + LIMITED_ALPHABET[offset - 10]

    # United States (Nxxxx)
    @staticmethod
    def n_reg(icao: int):
        result = "N"
        offset = icao - 0xA00001
        if offset < 0 or offset >= 915399:
            return None

        x = int(offset / 101711) + 1
        result += str(x)
        offset %= 101711
        if offset <= 600:
            # Na, NaA .. NaZ, NaAA .. NaZZ
            return result + IcaoRegistration.n_letters(offset)

        # Na0* .. Na9*
        offset -= 601
        x = int(offset / 10111)
        result += str(x)
        offset %= 10111
        if offset <= 600:
            # Nab, NabA..NabZ, NabAA..NabZZ
            return result + IcaoRegistration.n_letters(offset)

        # Nab0* .. Nab9*
        offset -= 601
        x = int(offset / 951)
        result += str(x)
        offset %= 951
        if offset <= 600:
            # Nabc, NabcA .. NabcZ, NabcAA .. NabcZZ
            return result + IcaoRegistration.n_letters(offset)

        # Nabc0* .. Nabc9*
        offset -= 601
        x = int(offset / 35)
        result += str(x)
        offset %= 35
        if offset <= 24:
            # Nabcd, NabcdA .. NabcdZ
            return result + IcaoRegistration.n_letter(offset)
        else:
            # Nabcd0 .. Nabcd9
            return result + str(offset - 25)

    @staticmethod
    def n_letters(x: int):
        if x <= 0:
            return ""
        else:
            x -= 1
            return LIMITED_ALPHABET[int(x / 25)] + IcaoRegistration.n_letter(x % 25)

    @staticmethod
    def n_letter(x: int):
        if x <= 0:
            return ""
        else:
            x -= 1
            return LIMITED_ALPHABET[x]


class StrideMapping(object):
    @staticmethod
    def find(icao: int):
        for mapping in STRIDE_MAPPINGS:
            result = mapping.getRegistration(icao)
            if result is not None:
                return result
        return None

    def __init__(self, start: int, s1: int, s2: int, prefix: str, first: str = None, last: str = None, alphabet: str = None):
        self.start  = start
        self.s1     = s1 
        self.s2     = s2
        self.prefix = prefix 
        self.first  = first
        self.last   = last
        self.alphabet = FULL_ALPHABET if alphabet is None else alphabet

        if not first:
            self.offset = 0
        else:
            x1 = self.alphabet.find(first[0])
            x2 = self.alphabet.find(first[1])
            x3 = self.alphabet.find(first[2])
            self.offset = x1 * s1 + x2 * s2 + x3

        if not last:
            x = len(self.alphabet) - 1
            self.end = self.start - self.offset + x * s1 + x * s2 + x
        else:
            x1 = self.alphabet.find(last[0])
            x2 = self.alphabet.find(last[1])
            x3 = self.alphabet.find(last[2])
            self.end = self.start - self.offset + x1 * s1 + x2 * s2 + x3

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getRegistration(self, icao: int):
        if not self.contains(icao):
            return None

        offset = icao - self.start + self.offset
        x1 = int(offset / self.s1)
        offset %= self.s1
        x2 = int(offset / self.s2)
        offset %= self.s2
        x3 = offset

        al = len(self.alphabet)
        if 0 <= x1 < al and 0 <= x2 < al and 0 <= x3 < al:
            return self.prefix + self.alphabet[x1] + self.alphabet[x2] + self.alphabet[x3]
        else:
            return None


class NumericMapping(object):
    @staticmethod
    def find(icao: int):
        for mapping in NUMERIC_MAPPINGS:
            result = mapping.getRegistration(icao)
            if result is not None:
                return result
        return None

    def __init__(self, start: int, first: int, count: int, template: str):
        self.start    = start
        self.end      = start + count - 1
        self.first    = first
        self.count    = count
        self.template = template

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getRegistration(self, icao: int):
        if not self.contains(icao):
            return None

        result = str(icao - self.start + self.first)
        return self.template[:len(self.template)-len(result)] + result


class IcaoCountry(object):
    @staticmethod
    def find(icao: int):
        for x in ICAO_COUNTRIES:
            if x.contains(icao):
                return (x.getCountryName(), x.getCountryCode())
        return None

    def __init__(self, start: int, end: int, name: str, code: str = None):
        self.start = start
        self.end   = end 
        self.name  = name
        self.code  = code

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getCountryName(self):
        return self.name

    def getCountryCode(self):
        return self.code


# 24 characters, without I/O
LIMITED_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"

# 26 characters
FULL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Numeric suffixes assigned with a regular pattern
# start    : start hexid in range
# first    : first numeric registration
# count    : number of numeric registrations
# template : template, trailing characters replaced with the number
NUMERIC_MAPPINGS = [
    NumericMapping(0x140000, 0,    100000, "RA-00000"),
    NumericMapping(0x0B03E8, 1000, 1000,   "CU-T0000"),
]

# Three-letter suffixes assigned with a regular pattern
# start    : first hexid of range
# s1       : major stride (interval between different first letters)
# s2       : minor stride (interval between different second letters)
# prefix   : the registration prefix
# alphabet : the alphabet to use (defaults to full_alphabet)
# first    : the suffix to use at the start of the range (default: AAA)
# last     : the last valid suffix in the range (default: ZZZ)
STRIDE_MAPPINGS = [
    # South African stride mapping apparently no longer in use
    #StrideMapping(0x008011, 26*26, 26, "ZS-"),

    StrideMapping(0x380000, 1024,  32, "F-B"),
    StrideMapping(0x388000, 1024,  32, "F-I"),
    StrideMapping(0x390000, 1024,  32, "F-G"),
    StrideMapping(0x398000, 1024,  32, "F-H"),
    StrideMapping(0x3A0000, 1024,  32, "F-O"),

    StrideMapping(0x3C4421, 1024,  32, "D-A", "AAA", "OZZ"),
    StrideMapping(0x3C0001, 26*26, 26, "D-A", "PAA", "ZZZ"),
    StrideMapping(0x3C8421, 1024,  32, "D-B", "AAA", "OZZ"),
    StrideMapping(0x3C2001, 26*26, 26, "D-B", "PAA", "ZZZ"),
    StrideMapping(0x3CC000, 26*26, 26, "D-C"),
    StrideMapping(0x3D04A8, 26*26, 26, "D-E"),
    StrideMapping(0x3D4950, 26*26, 26, "D-F"),
    StrideMapping(0x3D8DF8, 26*26, 26, "D-G"),
    StrideMapping(0x3DD2A0, 26*26, 26, "D-H"),
    StrideMapping(0x3E1748, 26*26, 26, "D-I"),

    StrideMapping(0x448421, 1024,  32, "OO-"),
    StrideMapping(0x458421, 1024,  32, "OY-"),
    StrideMapping(0x460000, 26*26, 26, "OH-"),
    StrideMapping(0x468421, 1024,  32, "SX-"),
    StrideMapping(0x490421, 1024,  32, "CS-"),
    StrideMapping(0x4A0421, 1024,  32, "YR-"),
    StrideMapping(0x4B8421, 1024,  32, "TC-"),
    StrideMapping(0x740421, 1024,  32, "JY-"),
    StrideMapping(0x760421, 1024,  32, "AP-"),
    StrideMapping(0x768421, 1024,  32, "9V-"),
    StrideMapping(0x778421, 1024,  32, "YK-"),
    StrideMapping(0xC00001, 26*26, 26, "C-F"),
    StrideMapping(0xC044A9, 26*26, 26, "C-G"),
    StrideMapping(0xE01041, 4096,  64, "LV-"),
]

# Mostly generated from the assignment table in the appendix to Chapter 9
# of Annex 10 Vol III, Second Edition, July 2007 (with amendments through
# 88-A, 14/11/2013)
ICAO_COUNTRIES = [
    IcaoCountry(0x004000, 0x0043FF, "Zimbabwe", "zw"),
    IcaoCountry(0x006000, 0x006FFF, "Mozambique", "mz"),
    IcaoCountry(0x008000, 0x00FFFF, "South Africa", "za"),
    IcaoCountry(0x010000, 0x017FFF, "Egypt", "eg"),
    IcaoCountry(0x018000, 0x01FFFF, "Lybia", "ly"),
    IcaoCountry(0x020000, 0x027FFF, "Morocco", "ma"),
    IcaoCountry(0x028000, 0x02FFFF, "Tunisia", "tn"),
    IcaoCountry(0x030000, 0x0303FF, "Botswana", "bw"),
    IcaoCountry(0x032000, 0x032FFF, "Burundi", "bi"),
    IcaoCountry(0x034000, 0x034FFF, "Cameroon", "cm"),
    IcaoCountry(0x035000, 0x0353FF, "Comoros", "km"),
    # "CD" for Democratic Republic of Congo, "CG" for Republic of Congo
    IcaoCountry(0x036000, 0x036FFF, "DR Congo", "cd"),
    IcaoCountry(0x038000, 0x038FFF, "Cote d'Ivoire", "ci"),
    IcaoCountry(0x03E000, 0x03EFFF, "Gabon", "ga"),
    IcaoCountry(0x040000, 0x040FFF, "Ethiopia", "et"),
    IcaoCountry(0x042000, 0x042FFF, "Equatorial Guinea", "gq"),
    IcaoCountry(0x044000, 0x044FFF, "Ghana", "gh"),
    IcaoCountry(0x046000, 0x046FFF, "Guinea", "gn"),
    IcaoCountry(0x048000, 0x0483FF, "Guinea-Bissau", "gw"),
    IcaoCountry(0x04A000, 0x04A3FF, "Lesotho", "ls"),
    IcaoCountry(0x04C000, 0x04CFFF, "Kenya", "ke"),
    IcaoCountry(0x050000, 0x050FFF, "Liberia", "lr"),
    IcaoCountry(0x054000, 0x054FFF, "Madagascar", "mg"),
    IcaoCountry(0x058000, 0x058FFF, "Malawi", "mw"),
    IcaoCountry(0x05A000, 0x05A3FF, "Maldives", "mv"),
    IcaoCountry(0x05C000, 0x05CFFF, "Mali", "ml"),
    IcaoCountry(0x05E000, 0x05E3FF, "Mauritania", "mr"),
    IcaoCountry(0x060000, 0x0603FF, "Mauritius", "mu"),
    IcaoCountry(0x062000, 0x062FFF, "Niger", "ne"),
    IcaoCountry(0x064000, 0x064FFF, "Nigeria", "ng"),
    IcaoCountry(0x068000, 0x068FFF, "Uganda", "ug"),
    IcaoCountry(0x06A000, 0x06A3FF, "Qatar", "qa"),
    IcaoCountry(0x06C000, 0x06CFFF, "Central African Republic", "cf"),
    IcaoCountry(0x06E000, 0x06EFFF, "Rwanda", "rw"),
    IcaoCountry(0x070000, 0x070FFF, "Senegal", "sn"),
    IcaoCountry(0x074000, 0x0743FF, "Seychelles", "sc"),
    IcaoCountry(0x076000, 0x0763FF, "Sierra Leone", "sl"),
    IcaoCountry(0x078000, 0x078FFF, "Somalia", "so"),
    IcaoCountry(0x07A000, 0x07A3FF, "Eswatini", "sz"),
    IcaoCountry(0x07C000, 0x07CFFF, "Sudan", "sd"),
    IcaoCountry(0x080000, 0x080FFF, "Tanzania", "tz"),
    IcaoCountry(0x084000, 0x084FFF, "Chad", "td"),
    IcaoCountry(0x088000, 0x088FFF, "Togo", "tg"),
    IcaoCountry(0x08A000, 0x08AFFF, "Zambia", "zm"),
    IcaoCountry(0x08C000, 0x08CFFF, "Congo", "cd"),
    IcaoCountry(0x090000, 0x090FFF, "Angola", "ao"),
    IcaoCountry(0x094000, 0x0943FF, "Benin", "bj"),
    IcaoCountry(0x096000, 0x0963FF, "Cabo Verde", "cv"),
    IcaoCountry(0x098000, 0x0983FF, "Djibouti", "dj"),
    IcaoCountry(0x09A000, 0x09AFFF, "Gambia", "gm"),
    IcaoCountry(0x09C000, 0x09CFFF, "Burkina Faso", "bf"),
    IcaoCountry(0x09E000, 0x09E3FF, "Sao Tome and Principe", "st"),
    IcaoCountry(0x0A0000, 0x0A7FFF, "Algeria", "dz"),
    IcaoCountry(0x0A8000, 0x0A8FFF, "Bahamas", "bs"),
    IcaoCountry(0x0AA000, 0x0AA3FF, "Barbados", "bb"),
    IcaoCountry(0x0AB000, 0x0AB3FF, "Belize", "bz"),
    IcaoCountry(0x0AC000, 0x0ACFFF, "Colombia", "co"),
    IcaoCountry(0x0AE000, 0x0AEFFF, "Costa Rica", "cr"),
    IcaoCountry(0x0B0000, 0x0B0FFF, "Cuba", "cu"),
    IcaoCountry(0x0B2000, 0x0B2FFF, "El Salvador", "sv"),
    IcaoCountry(0x0B4000, 0x0B4FFF, "Guatemala", "gt"),
    IcaoCountry(0x0B6000, 0x0B6FFF, "Guyana", "gy"),
    IcaoCountry(0x0B8000, 0x0B8FFF, "Haiti", "ht"),
    IcaoCountry(0x0BA000, 0x0BAFFF, "Honduras", "hn"),
    IcaoCountry(0x0BC000, 0x0BC3FF, "Saint Vincent and Grenadines", "vc"),
    IcaoCountry(0x0BE000, 0x0BEFFF, "Jamaica", "jm"),
    IcaoCountry(0x0C0000, 0x0C0FFF, "Nicaragua", "ni"),
    IcaoCountry(0x0C2000, 0x0C2FFF, "Panama", "pa"),
    IcaoCountry(0x0C4000, 0x0C4FFF, "Dominican Republic", "do"),
    IcaoCountry(0x0C6000, 0x0C6FFF, "Trinidad and Tobago", "tt"),
    IcaoCountry(0x0C8000, 0x0C8FFF, "Suriname", "sr"),
    IcaoCountry(0x0CA000, 0x0CA3FF, "Antigua and Barbuda", "ag"),
    IcaoCountry(0x0CC000, 0x0CC3FF, "Grenada", "gd"),
    IcaoCountry(0x0D0000, 0x0D7FFF, "Mexico", "mx"),
    IcaoCountry(0x0D8000, 0x0DFFFF, "Venezuela", "ve"),
    IcaoCountry(0x100000, 0x1FFFFF, "Russia", "ru"),
    IcaoCountry(0x201000, 0x2013FF, "Namibia", "na"),
    IcaoCountry(0x202000, 0x2023FF, "Eritrea", "er"),
    IcaoCountry(0x300000, 0x33FFFF, "Italy", "it"),
    IcaoCountry(0x340000, 0x37FFFF, "Spain", "es"),
    IcaoCountry(0x380000, 0x3BFFFF, "France", "fr"),
    IcaoCountry(0x3C0000, 0x3FFFFF, "Germany", "de"),

    # UK territories are officially part of the UK range, so adding
    # extra entries that are above the UK and thus take precedence
    IcaoCountry(0x400000, 0x4001BF, "Bermuda", "bm"),
    IcaoCountry(0x4001C0, 0x4001FF, "Cayman Islands", "ky"),
    IcaoCountry(0x400300, 0x4003FF, "Turks and Caicos", "tc"),
    IcaoCountry(0x424135, 0x4241F2, "Cayman Islands", "ky"),
    IcaoCountry(0x424200, 0x4246FF, "Bermuda", "bm"),
    IcaoCountry(0x424700, 0x424899, "Cayman Islands", "ky"),
    IcaoCountry(0x424B00, 0x424BFF, "Isle of Man", "im"),
    IcaoCountry(0x43BE00, 0x43BEFF, "Bermuda", "bm"),
    IcaoCountry(0x43E700, 0x43EAFD, "Isle of Man", "im"),
    IcaoCountry(0x43EAFE, 0x43EEFF, "Guernsey", "gg"),
    # Catch the rest of the United Kingdom
    IcaoCountry(0x400000, 0x43FFFF, "United Kingdom", "gb"),

    IcaoCountry(0x440000, 0x447FFF, "Austria", "at"),
    IcaoCountry(0x448000, 0x44FFFF, "Belgium", "be"),
    IcaoCountry(0x450000, 0x457FFF, "Bulgaria", "bg"),
    IcaoCountry(0x458000, 0x45FFFF, "Denmark", "dk"),
    IcaoCountry(0x460000, 0x467FFF, "Finland", "fi"),
    IcaoCountry(0x468000, 0x46FFFF, "Greece", "gr"),
    IcaoCountry(0x470000, 0x477FFF, "Hungary", "hu"),
    IcaoCountry(0x478000, 0x47FFFF, "Norway", "no"),
    IcaoCountry(0x480000, 0x487FFF, "Netherlands", "nl"),
    IcaoCountry(0x488000, 0x48FFFF, "Poland", "pl"),
    IcaoCountry(0x490000, 0x497FFF, "Portugal", "pt"),
    IcaoCountry(0x498000, 0x49FFFF, "Czechia", "cz"),
    IcaoCountry(0x4A0000, 0x4A7FFF, "Romania", "ro"),
    IcaoCountry(0x4A8000, 0x4AFFFF, "Sweden", "se"),
    IcaoCountry(0x4B0000, 0x4B7FFF, "Switzerland", "ch"),
    IcaoCountry(0x4B8000, 0x4BFFFF, "Turkey", "tr"),
    IcaoCountry(0x4C0000, 0x4C7FFF, "Serbia", "rs"),
    IcaoCountry(0x4C8000, 0x4C83FF, "Cyprus", "cy"),
    IcaoCountry(0x4CA000, 0x4CAFFF, "Ireland", "ie"),
    IcaoCountry(0x4CC000, 0x4CCFFF, "Iceland", "is"),
    IcaoCountry(0x4D0000, 0x4D03FF, "Luxembourg", "lu"),
    IcaoCountry(0x4D2000, 0x4D2FFF, "Malta", "mt"),
    IcaoCountry(0x4D4000, 0x4D43FF, "Monaco", "mc"),
    IcaoCountry(0x500000, 0x5003FF, "San Marino", "sm"),
    IcaoCountry(0x501000, 0x5013FF, "Albania", "al"),
    IcaoCountry(0x501C00, 0x501FFF, "Croatia", "hr"),
    IcaoCountry(0x502C00, 0x502FFF, "Latvia", "lv"),
    IcaoCountry(0x503C00, 0x503FFF, "Lithuania", "lt"),
    IcaoCountry(0x504C00, 0x504FFF, "Moldova", "md"),
    IcaoCountry(0x505C00, 0x505FFF, "Slovakia", "sk"),
    IcaoCountry(0x506C00, 0x506FFF, "Slovenia", "si"),
    IcaoCountry(0x507C00, 0x507FFF, "Uzbekistan", "uz"),
    IcaoCountry(0x508000, 0x50FFFF, "Ukraine", "ua"),
    IcaoCountry(0x510000, 0x5103FF, "Belarus", "by"),
    IcaoCountry(0x511000, 0x5113FF, "Estonia", "ee"),
    IcaoCountry(0x512000, 0x5123FF, "Macedonia", "mk"),
    IcaoCountry(0x513000, 0x5133FF, "Bosnia and Herzegovina", "ba"),
    IcaoCountry(0x514000, 0x5143FF, "Georgia", "ge"),
    IcaoCountry(0x515000, 0x5153FF, "Tajikistan", "tj"),
    IcaoCountry(0x516000, 0x5163FF, "Montenegro", "me"),
    IcaoCountry(0x600000, 0x6003FF, "Armenia", "am"),
    IcaoCountry(0x600800, 0x600BFF, "Azerbaijan", "az"),
    IcaoCountry(0x601000, 0x6013FF, "Kyrgyzstan", "kg"),
    IcaoCountry(0x601800, 0x601BFF, "Turkmenistan", "tm"),
    IcaoCountry(0x680000, 0x6803FF, "Bhutan", "bt"),
    IcaoCountry(0x681000, 0x6813FF, "Micronesia", "fm"),
    IcaoCountry(0x682000, 0x6823FF, "Mongolia", "mn"),
    IcaoCountry(0x683000, 0x6833FF, "Kazakhstan", "kz"),
    IcaoCountry(0x684000, 0x6843FF, "Palau", "pw"),
    IcaoCountry(0x700000, 0x700FFF, "Afghanistan", "af"),
    IcaoCountry(0x702000, 0x702FFF, "Bangladesh", "bd"),
    IcaoCountry(0x704000, 0x704FFF, "Myanmar", "mm"),
    IcaoCountry(0x706000, 0x706FFF, "Kuwait", "kw"),
    IcaoCountry(0x708000, 0x708FFF, "Laos", "la"),
    IcaoCountry(0x70A000, 0x70AFFF, "Nepal", "np"),
    IcaoCountry(0x70C000, 0x70C3FF, "Oman", "om"),
    IcaoCountry(0x70E000, 0x70EFFF, "Cambodia", "kh"),
    IcaoCountry(0x710000, 0x717FFF, "Saudi Arabia", "sa"),
    IcaoCountry(0x718000, 0x71FFFF, "South Korea", "kr"),
    IcaoCountry(0x720000, 0x727FFF, "North Korea", "kp"),
    IcaoCountry(0x728000, 0x72FFFF, "Iraq", "iq"),
    IcaoCountry(0x730000, 0x737FFF, "Iran", "ir"),
    IcaoCountry(0x738000, 0x73FFFF, "Israel", "il"),
    IcaoCountry(0x740000, 0x747FFF, "Jordan", "jo"),
    IcaoCountry(0x748000, 0x74FFFF, "Lebanon", "lb"),
    IcaoCountry(0x750000, 0x757FFF, "Malaysia", "my"),
    IcaoCountry(0x758000, 0x75FFFF, "Philippines", "ph"),
    IcaoCountry(0x760000, 0x767FFF, "Pakistan", "pk"),
    IcaoCountry(0x768000, 0x76FFFF, "Singapore", "sg"),
    IcaoCountry(0x770000, 0x777FFF, "Sri Lanka", "lk"),
    IcaoCountry(0x778000, 0x77FFFF, "Syria", "sy"),
    IcaoCountry(0x789000, 0x789FFF, "Hong Kong", "hk"),
    IcaoCountry(0x780000, 0x7BFFFF, "China", "cn"),
    IcaoCountry(0x7C0000, 0x7FFFFF, "Australia", "au"),
    IcaoCountry(0x800000, 0x83FFFF, "India", "in"),
    IcaoCountry(0x840000, 0x87FFFF, "Japan", "jp"),
    IcaoCountry(0x880000, 0x887FFF, "Thailand", "th"),
    IcaoCountry(0x888000, 0x88FFFF, "Viet Nam", "vn"),
    IcaoCountry(0x890000, 0x890FFF, "Yemen", "ye"),
    IcaoCountry(0x894000, 0x894FFF, "Bahrain", "bh"),
    IcaoCountry(0x895000, 0x8953FF, "Brunei", "bn"),
    IcaoCountry(0x896000, 0x896FFF, "United Arab Emirates", "ae"),
    IcaoCountry(0x897000, 0x8973FF, "Solomon Islands", "sb"),
    IcaoCountry(0x898000, 0x898FFF, "Papua New Guinea", "pg"),
    IcaoCountry(0x899000, 0x8993FF, "Taiwan", "tw"),
    IcaoCountry(0x8A0000, 0x8A7FFF, "Indonesia", "id"),
    IcaoCountry(0x900000, 0x9003FF, "Marshall Islands", "mh"),
    IcaoCountry(0x901000, 0x9013FF, "Cook Islands", "sk"),
    IcaoCountry(0x902000, 0x9023FF, "Samoa", "ws"),
    IcaoCountry(0xA00000, 0xAFFFFF, "United States", "us"),
    IcaoCountry(0xC00000, 0xC3FFFF, "Canada", "ca"),
    IcaoCountry(0xC80000, 0xC87FFF, "New Zealand", "nz"),
    IcaoCountry(0xC88000, 0xC88FFF, "Fiji", "fj"),
    IcaoCountry(0xC8A000, 0xC8A3FF, "Nauru", "nr"),
    IcaoCountry(0xC8C000, 0xC8C3FF, "Saint Lucia", "lc"),
    IcaoCountry(0xC8D000, 0xC8D3FF, "Tonga", "to"),
    IcaoCountry(0xC8E000, 0xC8E3FF, "Kiribati", "ki"),
    IcaoCountry(0xC90000, 0xC903FF, "Vanuatu", "vu"),
    IcaoCountry(0xE00000, 0xE3FFFF, "Argentina", "ar"),
    IcaoCountry(0xE40000, 0xE7FFFF, "Brazil", "br"),
    IcaoCountry(0xE80000, 0xE80FFF, "Chile", "cl"),
    IcaoCountry(0xE84000, 0xE84FFF, "Ecuador", "ec"),
    IcaoCountry(0xE88000, 0xE88FFF, "Paraguay", "py"),
    IcaoCountry(0xE8C000, 0xE8CFFF, "Peru", "pe"),
    IcaoCountry(0xE90000, 0xE90FFF, "Uruguay", "uy"),
    IcaoCountry(0xE94000, 0xE94FFF, "Bolivia", "bo"),
    IcaoCountry(0xF00000, 0xF07FFF, "ICAO (temporary)"),
    IcaoCountry(0xF09000, 0xF093FF, "ICAO (special use)"),

    # Block assignments mentioned in Chapter 9 section 4, at the end so they
    # are only used if nothing above applies
    IcaoCountry(0x200000, 0x27FFFF, "Unassigned (AFI region)"),
    IcaoCountry(0x280000, 0x28FFFF, "Unassigned (SAM region)"),
    IcaoCountry(0x500000, 0x5FFFFF, "Unassigned (EUR / NAT regions)"),
    IcaoCountry(0x600000, 0x67FFFF, "Unassigned (MID region)"),
    IcaoCountry(0x680000, 0x6FFFFF, "Unassigned (ASIA region)"),
    IcaoCountry(0x900000, 0x9FFFFF, "Unassigned (NAM / PAC regions)"),
    IcaoCountry(0xB00000, 0xBFFFFF, "Unassigned (reserved for future use)"),
    IcaoCountry(0xEC0000, 0xEFFFFF, "Unassigned (CAR region)"),
    IcaoCountry(0xD00000, 0xDFFFFF, "Unassigned (reserved for future use)"),
    IcaoCountry(0xF00000, 0xFFFFFF, "Unassigned (reserved for future use)"),
]
