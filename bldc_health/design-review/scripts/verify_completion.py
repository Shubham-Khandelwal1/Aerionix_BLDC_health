"""Check exported connectivity and physical pad numbering, independent of ERC."""
from pathlib import Path
import json, xml.etree.ElementTree as ET
from sexp_tools import read,many,one,libsym

base=Path(__file__).resolve().parents[2]
out=base/'completion'
netlist=ET.parse(out/'bldc_health.net.xml')
actual={f"{n.attrib['ref']}.{n.attrib['pin']}": net.attrib['name'].removeprefix('/')
        for net in netlist.findall('./nets/net') for n in net}
expect=json.loads((out/'expected-connections.json').read_text())
errors=[]
for key,net in expect['nets'].items():
    if key.startswith('#'):continue # KiCad deliberately omits virtual power flags.
    if actual.get(key)!=net:errors.append(f'{key}: expected {net}, got {actual.get(key)}')
for key in expect['no_connect']:
    if not actual.get(key,'').startswith('unconnected-'):errors.append(f'{key}: missing NC marker')

# Functional requirements, independently named and grouped.
groups=[
 ['U1.44','U2.13','R4.2'], ['U1.45','U2.14','R3.2'],
 ['U1.16','U3.23','R7.2'], ['U1.30','U3.24','R6.2'],
 ['U1.33','J1.A7','J1.B7','U5.1','U5.6'],
 ['U1.34','J1.A6','J1.B6','U5.3','U5.4'],
 ['U1.36','J2.2'], ['U1.37','J2.4'], ['U1.41','J2.6'],
 ['U1.7','J2.10','R8.2','C18.1','SW1.1'],
 ['U1.46','R9.1','JP1.2'], ['U1.8','R11.2','C19.1','D1.3'],
 ['U1.20','U1.21','FB2.2','R10.1','C16.1','C17.1'],
 ['U1.49','U3.11','U3.18','U3.20','U2.7','J1.SH','J4.2'],
 ['U1.17','U2.4'],['U1.18','U2.9'],['U1.19','U3.12'],['U1.29','U3.19']]
for group in groups:
    if len({actual.get(k) for k in group})!=1 or any(k not in actual for k in group):
        errors.append('Required connection missing: '+', '.join(group))
if actual['U1.33']==actual['U1.34']:errors.append('USB data pair shorted')
if actual['U4.1']==actual['U4.5']:errors.append('LDO input/output shorted')
if actual['U1.48']==actual['U1.49']:errors.append('MCU power/ground shorted')

comps=netlist.findall('./components/comp')
for comp in comps:
    ref=comp.attrib['ref'];fp=comp.findtext('footprint')
    if not fp:errors.append(f'{ref}: no footprint');continue
    lib,name=fp.split(':',1)
    p=((out/'BLDC_Health.pretty') if lib=='BLDC_Health' else Path('/usr/share/kicad/footprints')/(lib+'.pretty'))/(name+'.kicad_mod')
    if not p.exists():errors.append(f'{ref}: footprint file missing');continue
    pads={str(v[1]) for v in many(read(p),'pad') if v[1]}
    pins={key.split('.',1)[1] for key in actual if key.startswith(ref+'.')}
    if pads!=pins:errors.append(f'{ref}: pad/pin mismatch {pads ^ pins}')

# Cross-check all original MCU pin numbers against KiCad's independent symbol.
local=read(out/'BLDC_Health.kicad_sym')
mcu=next(s for s in many(local,'symbol') if s[1]=='STM32G491CCU6')
def pins(sym):
    return {one(p,'number')[1]:one(p,'name')[1].split('-')[0]
            for unit in many(sym,'symbol') for p in many(unit,'pin')}
if pins(mcu)!=pins(libsym('MCU_ST_STM32G4','STM32G491CCUx')):
    errors.append('MCU pin numbering differs from the standard UFQFPN48 symbol')

erc=json.loads((out/'erc.json').read_text())
violations=[v for sheet in erc['sheets'] for v in sheet['violations']]
if violations:errors.append(f'ERC reports {len(violations)} violations')
project=json.loads((out/'bldc_health.kicad_pro').read_text())
if project['erc'].get('erc_exclusions'):errors.append('Unexpected ERC exclusions')

result='PASS' if not errors else 'FAIL'
lines=[f'Schematic validation: {result}',f'KiCad ERC: {len(violations)} violations; no exclusions',
       f'Connected physical pins checked: {sum(not k.startswith("#") for k in expect["nets"])}',
       f'Explicit no-connect pins checked: {len(expect["no_connect"])}',
       f'Independent functional connection groups checked: {len(groups)}',
       f'Components with matching footprint pad sets: {len(comps)}',
       'All 49 MCU pins cross-checked against the standard STM32G491CCUx symbol.',
       'Scope: schematic/netlist checks only; no routed PCB or hardware tests.',*errors]
(out/'VALIDATION.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
if errors:raise SystemExit(1)
