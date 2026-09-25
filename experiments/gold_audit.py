import sys, collections, unicodedata
sys.path.insert(0, "src")
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a

kinds = collections.Counter()
datetime_len = collections.Counter()
punct = collections.Counter()
total = 0
for d in iter_documents(cardiode_a()):
    for m in d.mentions:
        total += 1
        kinds[m.type] += 1
        if m.type == "DATETIME":
            n = m.span.end - m.span.start
            datetime_len[min(n, 2)] += 1
            if n == 1:
                punct[unicodedata.category(d.text[m.span.start])] += 1
print(f"total gold mentions            {total}")
print(f"  DATETIME                     {kinds['DATETIME']}")
print(f"    length 1                   {datetime_len[1]}  ({100*datetime_len[1]/total:.1f}% of ALL gold)")
print(f"    length >1                  {datetime_len[2]}")
print(f"  unicode category of the 1-char DATETIME spans: {dict(punct)}")
print(f"    (Ps/Pe = open/close bracket, Pd = dash, Zs = space)")
print("\nall types:", dict(kinds.most_common()))
