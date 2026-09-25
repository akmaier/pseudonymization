'''How many of the 8,696 display names are single-token, and what does the filter do to them?'''
import sys
sys.path.insert(0, 'src')
from pseudonymkit.adapters import enron
from pseudonymkit.adapters.enron import is_person_name, _person_name_gazetteer
from pseudonymkit.paths import shared_corpora

src = shared_corpora() / 'enron' / 'enron_mail_20150507.tar.gz'
table = enron.build_identity_table(raw for _, _, raw in enron.iter_raw_messages(src))
frequent = [n for n in table.names() if table.counts.get(n, 0) >= 2]
g = _person_name_gazetteer()
one = [n for n in frequent if ' ' not in n and ',' not in n]
multi = [n for n in frequent if n not in set(one)]
kept_one = [n for n in one if is_person_name(n, g)]
print(f'display names seen >=2x : {len(frequent):,}')
print(f'  multi-part (exempt)   : {len(multi):,}  ({len(multi)/len(frequent):5.1%})  all kept')
print(f'  single-token          : {len(one):,}  ({len(one)/len(frequent):5.1%})')
print(f'      kept as people    : {len(kept_one):,}  ({len(kept_one)/max(len(one),1):5.1%} of single-token)')
print(f'      dropped as roles  : {len(one)-len(kept_one):,}  ({(len(one)-len(kept_one))/max(len(one),1):5.1%} of single-token)')
