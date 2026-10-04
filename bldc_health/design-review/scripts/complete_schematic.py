"""Build a reviewable completion copy; never overwrite the user's open project.

Core symbol geometries and the IMU footprints come from the original design.
All generated schematic symbols are included in a project-local native library.
"""
from sexp_tools import *
import math, uuid, shutil

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'completion'
OUT.mkdir(exist_ok=True)
A = Atom
def uid(): return str(uuid.uuid4())
def node(k,*v): return [A(k),*v]
def q(v): return round(v/1.27)*1.27
def effects(size=1.0,justify=None):
    e=node('effects',node('font',node('size',size,size)))
    if justify:e.append(node('justify',*[A(x) for x in justify.split()]))
    return e
def field(key,value,x,y,hide=False,size=1.0):
    p=node('property',key,value,node('at',x,y,0),effects(size))
    if hide: p[-1].append(node('hide',A('yes')))
    return p

original=read(BASE/'bldc_health.kicad_sch')
original_lib={s[1]:s for s in many(one(original,'lib_symbols'),'symbol')}
original_ids={prop(s,'Reference')[2]:one(s,'uuid')[1] for s in many(original,'symbol')}
root_id=uid()
root=node('kicad_sch',node('version',20260306),node('generator',A('eeschema')),
          node('generator_version','10.0'),node('uuid',root_id),node('paper','A3'),
          node('title_block',node('title','BLDC motor health monitor'),node('date','2026-10-02'),
               node('rev','A - review copy'),node('comment',1,'USB-powered | dual I2C IMUs | proposed remote NTC temperature input')))
libcache=node('lib_symbols');root.append(libcache)
library=node('kicad_symbol_lib',node('version',20241209),node('generator',A('kicad_symbol_editor')))
symbols={};instances={};pinmap={};expected={};nc_expected=set()

def add_library(lib,name):
    key=name
    if key in symbols:return key
    s=libsym(lib,name)
    s[1]=key
    # Project-local immutable copies retain the electrical types from KiCad.
    for p in many(s,'property'):
        if p[1]=='Reference':p[2]='#FLG' if name=='PWR_FLAG' else p[2]
    library.append(copy.deepcopy(s))
    embedded=copy.deepcopy(s);embedded[1]='BLDC_Health:'+key
    libcache.append(embedded);symbols[key]=s
    return key

def core(name,types,footprint,url):
    s=copy.deepcopy(original_lib['EasyEDA_Lib:'+name]);s[1]=name
    s[:]=[x for x in s if not(isinstance(x,list) and x and x[0]=='property' and x[1] not in ['Reference','Value','Footprint','Datasheet','Description'])]
    prop(s,'Value')[2]=name;prop(s,'Footprint')[2]=footprint;prop(s,'Datasheet')[2]=url
    for u in many(s,'symbol'):
        for p in many(u,'pin'):
            num=one(p,'number')[1];p[1]=A(types.get(num,'bidirectional'))
            if name=='ICM-40609-D' and num=='19':one(p,'name')[1]='INT2/FSYNC'
    library.append(copy.deepcopy(s));embedded=copy.deepcopy(s);embedded[1]='BLDC_Health:'+name
    libcache.append(embedded);symbols[name]=s

core('STM32G491CCU6',{**{str(i):'power_in' for i in [1,21,23,35,48,49]},'20':'input'},
     'Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm','https://www.st.com/resource/en/datasheet/stm32g491cc.pdf')
core('ASM330LHHXTR',{'1':'bidirectional','2':'passive','3':'passive','4':'output','5':'power_in','6':'no_connect',
     '7':'power_in','8':'power_in','9':'output','10':'no_connect','11':'no_connect','12':'input','13':'input','14':'bidirectional'},
     'BLDC_Health:LGA-14_L3.0-W2.5-P0.50-TL','https://www.st.com/resource/en/datasheet/asm330lhhx.pdf')
core('ICM-40609-D',{**{str(i):'no_connect' for i in [1,2,3,4,5,6,7,10,14,15,16,17,21]},
     '8':'power_in','9':'bidirectional','11':'passive','12':'output','13':'power_in','18':'power_in','19':'bidirectional','20':'passive','22':'input','23':'input','24':'bidirectional'},
     'BLDC_Health:LGA-24_L3.0-W3.0-P0.40-TL','https://product.tdk.com/system/files/dam/doc/product/sensor/mortion-inertial/imu/data_sheet/ds-000330_icm-40609-d_v1.2.pdf')

def inst(key,ref,x,y,value=None,fp=None,rot=0,fy=None):
    x,y=q(x),q(y);s=symbols[key]
    if value is None:value=prop(s,'Value')[2]
    if fp is None:fp=prop(s,'Footprint')[2]
    n=node('symbol',node('lib_id','BLDC_Health:'+key),node('at',x,y,rot),node('unit',1),
           node('exclude_from_sim',A('no')),node('in_bom',A('no' if ref.startswith('#') else 'yes')),
           node('on_board',A('yes')),node('dnp',A('no')),node('uuid',original_ids.get(ref,uid())))
    if fy is None:fy=y-7.62
    n.extend([field('Reference',ref,x,fy,ref.startswith('#')),field('Value',value,x,fy+2.54,ref.startswith('#')),
              field('Footprint',fp,x,y,True),field('Datasheet',prop(s,'Datasheet')[2] if prop(s,'Datasheet') else '',x,y,True)])
    n.append(node('instances',node('project','bldc_health',node('path','/'+root_id,node('reference',ref),node('unit',1)))))
    root.append(n);instances[ref]=n
    for u in many(s,'symbol'):
        for p in many(u,'pin'):
            number=one(p,'number')[1];a=one(p,'at');theta=math.radians(rot)
            px=x+a[1]*math.cos(theta)-a[2]*math.sin(theta)
            py=y-a[1]*math.sin(theta)-a[2]*math.cos(theta)
            angle=(a[3]+rot)%360
            pinmap[(ref,number)]=(round(px,6),round(py,6),angle,p[1])
    return ref
def std(lib,key,ref,x,y,**kw):return inst(add_library(lib,key),ref,x,y,**kw)
def wire(a,b):
    if a==b:return
    root.append(node('wire',node('pts',node('xy',*a),node('xy',*b)),node('stroke',node('width',0),node('type',A('default'))),node('uuid',uid())))
def dot(p):root.append(node('junction',node('at',*p),node('diameter',0),node('color',0,0,0,0),node('uuid',uid())))
def label(name,x,y,angle=0):
    root.append(node('label',name,node('at',x,y,angle),effects(0.95,'right bottom' if angle==180 else 'left bottom'),node('uuid',uid())))
def nc(ref,num):
    num=str(num);x,y,_,_=pinmap[(ref,num)]
    if (ref,num) in nc_expected:return
    nc_expected.add((ref,num));root.append(node('no_connect',node('at',x,y),node('uuid',uid())))
seen=set()
def net(ref,num,name,length=3.81):
    num=str(num);x,y,ang,_=pinmap[(ref,num)];expected[(ref,num)]=name
    # Stacked connector pins share a single visible wire and label.
    k=(x,y,name)
    if k in seen:return
    seen.add(k)
    dx=-math.cos(math.radians(ang))*length;dy=math.sin(math.radians(ang))*length
    end=(round(x+dx,6),round(y+dy,6));wire((x,y),end)
    label(name,*end,180 if ang==0 else 0)
def text(txt,x,y,size=1.15):
    root.append(node('text',txt,node('at',x,y,0),effects(size,'left top'),node('uuid',uid())))
def box(title,x1,y1,x2,y2):
    if x1==10:x1=15
    if x2==410:x2=405
    if y1==10:y1=15
    root.append(node('polyline',node('pts',*[node('xy',*p) for p in [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]]),
                     node('stroke',node('width',0.254),node('type',A('default'))),node('fill',node('type',A('none'))),node('uuid',uid())))
    text(title,x1+3,y1+2,1.6)

RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0603_1608Metric'
def resistor(ref,val,x,y,a,b,rot=0,fp=RFP):
    std('Device','R_Small',ref,x,y,value=val,fp=fp,rot=rot)
    net(ref,1,a);net(ref,2,b)
def cap(ref,val,x,y,rail='+3V3',fp=CFP):
    std('Device','C_Small',ref,x,y,value=val,fp=fp)
    net(ref,1,rail);net(ref,2,'GND')
def flag(ref,name,x,y):
    std('power','PWR_FLAG',ref,x,y);net(ref,1,name,0)

box('USB-C / 3.3 V power',10,10,145,105)
std('Connector','USB_C_Receptacle_USB2.0_16P','J1',29.21,49.53,value='USB4105-GF-A',
    fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',fy=24.13)
for p in ['A4','A9','B4','B9']:net('J1',p,'VBUS_USB')
for p in ['A1','A12','B1','B12','SH']:net('J1',p,'GND')
for p in ['A6','B6']:net('J1',p,'USB_DP')
for p in ['A7','B7']:net('J1',p,'USB_DM')
net('J1','A5','CC1');net('J1','B5','CC2');nc('J1','A8');nc('J1','B8')
resistor('R1','5.1k 1%',76.2,33.02,'CC1','GND')
resistor('R2','5.1k 1%',99.06,33.02,'CC2','GND')
std('Device','Polyfuse_Small','F2',78.74,22.86,value='1206L025YR',fp='Fuse:Fuse_1206_3216Metric',rot=90,fy=16.51)
net('F2',1,'VBUS_USB');net('F2',2,'VBUS_FUSED')
std('Jumper','SolderJumper_2_Bridged','JP2',120.65,22.86,value='POWER LINK',
    fp='Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm',fy=16.51)
net('JP2',1,'VBUS_FUSED');net('JP2',2,'+5V')
std('Regulator_Linear','AP2112K-3.3','U4',107.95,60.96,value='AP2112K-3.3TRG1',fy=48.26)
net('U4',1,'+5V');net('U4',3,'+5V');net('U4',2,'GND');net('U4',5,'+3V3');nc('U4',4)
cap('C1','4.7u / 10V',76.2,67.31,'+5V',fp='Capacitor_SMD:C_0805_2012Metric')
cap('C2','4.7u / 10V',130.81,67.31,fp='Capacitor_SMD:C_0805_2012Metric')
std('Power_Protection','USBLC6-2SC6','U5',41.91,87.63,fy=77.47)
for p in [1,6]:net('U5',p,'USB_DM')
for p in [3,4]:net('U5',p,'USB_DP')
net('U5',5,'VBUS_USB');net('U5',2,'GND')
text('U5 beside J1; 90 ohm differential pair.\nMCU has an internal USB D+ pull-up.\n5 V USB supply only; no motor supply input.',72,84,1.1)

box('MCU supply / reference / decoupling',150,10,280,105)
std('Device','FerriteBead_Small','FB2',179.07,31.75,value='120R @100MHz',
    fp='Inductor_SMD:L_0603_1608Metric',rot=90,fy=24.13)
net('FB2',1,'+3V3');net('FB2',2,'+3V3_A')
cap('C3','1u / 10V',213.36,30.48,'+3V3_A')
cap('C4','100n / 16V',245.11,30.48,'+3V3_A')
cap('C16','1u / 10V',179.07,53.34,'+3V3_A')
cap('C17','100n / 16V',213.36,53.34,'+3V3_A')
text('C3/C4 at VDDA (21).\nC16/C17 at VREF+ (20).\nKeep VREFBUF disabled.',235,45,1.0)
for ref,val,x in [('C8','4.7u / 10V',163.83),('C9','100n / 16V',187.96),('C10','100n / 16V',212.09),('C11','100n / 16V',236.22),('C12','100n / 16V',260.35)]:
    cap(ref,val,x,78.74)
text('C9/C10/C11: one per VDD pin 23/35/48. C12: VBAT pin 1.\nSolder exposed pad 49 to GND with a via array. X7R/X5R capacitors.',155,92,1.05)
flag('#FLG01','+5V',165.1,41.91);flag('#FLG02','GND',264.16,41.91)
flag('#FLG03','+3V3_A',264.16,22.86)

box('ASM330LHHXTR / I2C1 / address 0x6A',285,10,410,105)
inst('ASM330LHHXTR','U2',342.9,45.72,fy=22.86)
for p in [5,8,12]:net('U2',p,'+3V3')
for p in [2,3,7]:net('U2',p,'GND')
for p in [6,10,11]:nc('U2',p)
net('U2',1,'ASM_SA0');net('U2',4,'ASM_INT1');net('U2',9,'ASM_INT2')
net('U2',13,'I2C1_SCL');net('U2',14,'I2C1_SDA')
resistor('R3','4.7k',385,40.64,'+3V3','I2C1_SDA')
resistor('R4','4.7k',385,62.23,'+3V3','I2C1_SCL')
std('Jumper','SolderJumper_3_Bridged12','JP7',307.34,74.93,value='ASM ADDR',
    fp='Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm',fy=64.77)
net('JP7',1,'GND');net('JP7',2,'ASM_SA0');net('JP7',3,'+3V3')
cap('C5','100n',336.55,78.74);cap('C6','100n',360.68,78.74)
cap('C7','10u / 10V',384.81,83.82,fp='Capacitor_SMD:C_0805_2012Metric')
text('JP7: 1-2 closed = 0x6A; 2-3 = 0x6B. Never bridge all three.\nC5 at VDDIO (5); C6/C7 at VDD (8). MSDA/MSCL tied low.',290,95,1.0)

box('STM32G491CCU6 / UFQFPN48 + exposed pad',10,110,145,217)
inst('STM32G491CCU6','U1',76.2,166.37,fy=125.73)
mcu={1:'+3V3',7:'NRST',8:'TEMP_ADC',10:'UART2_TX',11:'UART2_RX',16:'I2C2_SCL',17:'ASM_INT1',18:'ASM_INT2',
     19:'ICM_INT1',20:'+3V3_A',21:'+3V3_A',23:'+3V3',29:'ICM_INT2',30:'I2C2_SDA',
     33:'USB_DM',34:'USB_DP',35:'+3V3',36:'SWDIO',37:'SWCLK',41:'SWO',44:'I2C1_SCL',45:'I2C1_SDA',
     46:'BOOT0',48:'+3V3',49:'GND'}
for p in range(1,50):
    if p in mcu:net('U1',p,mcu[p])
    else:nc('U1',p)
text('HSI16 + PLL for CPU. USB: HSI48 with CRS/SOF trimming.\nPA0 = ADC1_IN1. Unused GPIOs: analog mode in firmware.',20,205,1.0)

box('ICM-40609-D / I2C2 / address 0x68',150,110,280,217)
inst('ICM-40609-D','U3',212.09,152.4,fy=122.0)
for p in [8,13,22]:net('U3',p,'+3V3')
for p in [11,18,20]:net('U3',p,'GND')
for p in [1,2,3,4,5,6,7,10,14,15,16,17,21]:nc('U3',p)
net('U3',9,'ICM_AD0');net('U3',12,'ICM_INT1');net('U3',19,'ICM_INT2')
net('U3',23,'I2C2_SCL');net('U3',24,'I2C2_SDA')
resistor('R6','4.7k',261.62,133.35,'+3V3','I2C2_SDA')
resistor('R7','4.7k',261.62,161.29,'+3V3','I2C2_SCL')
std('Jumper','SolderJumper_3_Bridged12','JP6',173.99,190.5,value='ICM ADDR',
    fp='Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm',fy=180.34)
net('JP6',1,'GND');net('JP6',2,'ICM_AD0');net('JP6',3,'+3V3')
cap('C13','100n',207.01,193.04);cap('C14','2.2u / 10V',231.14,193.04);cap('C15','10n',257.81,193.04)
text('JP6: 1-2 closed = 0x68; 2-3 = 0x69. Pins 11/20 to GND.\nC13/C14 at VDD (13); C15 at VDDIO (8). Pin 19: INT2 output.',155,206,1.0)

box('SWD / reset / boot / UART',285,110,410,178)
std('Connector','Conn_ARM_JTAG_SWD_10','J2',309.88,144.78,value='ARM SWD 1.27mm',
    fp='Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical',fy=120.65)
for p,n in {1:'+3V3',2:'SWDIO',3:'GND',4:'SWCLK',5:'GND',6:'SWO',10:'NRST'}.items():net('J2',p,n)
wire(pinmap[('J2','9')][:2],pinmap[('J2','3')][:2]);expected[('J2','9')]='GND'
nc('J2',7);nc('J2',8)
resistor('R8','10k',353.06,130.81,'+3V3','NRST')
cap('C18','100n',376.0,130.81,'NRST')
std('Switch','SW_Push','SW1',394.97,142.24,value='RESET',fp='Button_Switch_SMD:SW_SPST_TL3342')
net('SW1',1,'NRST');net('SW1',2,'GND')
resistor('R9','10k',353.06,158.75,'BOOT0','GND')
std('Jumper','SolderJumper_2_Open','JP1',378.46,154.94,value='BOOT HIGH',
    fp='Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm')
net('JP1',1,'+3V3');net('JP1',2,'BOOT0')
std('Connector_Generic','Conn_01x03','J3',400.05,166.37,value='UART 3V3',
    fp='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',fy=157.48)
net('J3',1,'GND');net('J3',2,'UART2_TX');net('J3',3,'UART2_RX')
text('J2 pin 1 = target sense. Power through USB.\nBOOT jumper depends on STM32 option-byte settings.',290,166.5,0.95)

box('Proposed temperature input / remote 10k NTC',285,183,410,247)
std('Connector_Generic','Conn_01x02','J4',302.26,208.28,value='REMOTE NTC',
    fp='Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',fy=193.04)
net('J4',1,'NTC_RAW');net('J4',2,'GND')
resistor('R10','10k 0.1%',327.66,204.47,'+3V3_A','NTC_RAW')
resistor('R11','1k',358.14,205.74,'NTC_RAW','TEMP_ADC',rot=90)
cap('C19','100n',388.62,215.9,'TEMP_ADC')
std('Diode','BAT54S','D1',350.52,226.06,fy=215.9)
net('D1',1,'GND');net('D1',2,'+3V3_A');net('D1',3,'TEMP_ADC')
text('10k NTC at 25 C, B25/85 = 3977 K; e.g. NTCLE100E3103JB0.\nProbe between J4 pins 1/2; insulate electrically from motor.\nRatiometric ADC: open = high, short = low. Confirm probe choice.',290,236,0.95)

box('Implementation notes / bring-up assumptions',10,222,280,281)
text('1. Preserve separate I2C buses: PB6/PB7 = I2C1 AF4; PC4/PA8 = I2C2 AF4. Start at 400 kHz.\n'
     '2. 4.7k pull-ups assume short PCB traces and <= 75 pF bus capacitance. Verify rise time on hardware.\n'
     '3. Begin at <= 1 ksample/s per IMU with FIFO bursts. Full 32 kHz acquisition requires an SPI redesign.\n'
     '4. IMU interrupts: PB0/PB1 = ASM INT1/INT2; PB2/PC6 = ICM INT1/INT2. Configure U3 pin 19 as INT2.\n'
     '5. Keep IMUs rigidly coupled to the motor housing, away from board flex, fasteners, and regulator heat.\n'
     '6. USB crystal-less operation is specified for -15 to +85 C. HSI48 requires CRS synchronization.\n'
     '7. AP2112 replaces AMS1117 to support ceramic capacitors and improve dropout headroom.\n'
     '8. NTC is a proposed circuit, not a confirmed sensor requirement. Use calibrated vendor R/T data.\n'
     '9. Verify USB input inrush, suspend current, regulator temperature and probe noise on the prototype.\n'
     '10. Schematics only: PCB placement/routing and fabrication review remain. See DESIGN_NOTES.txt.',20,232,1.15)

# Field positions are global, but KiCad field text angles are relative to the
# instance orientation. Keep passive values beside vertical bodies and all text horizontal.
for ref,n in instances.items():
    key=one(n,'lib_id')[1].split(':',1)[1];_,x,y,rot=one(n,'at')
    for p in many(n,'property'):one(p,'at')[3]=rot
    if key in ['C_Small','R_Small'] and rot==0:
        for key2,dy in [('Reference',-1.27),('Value',1.27)]:
            p=prop(n,key2);one(p,'at')[1:3]=[x+2.54,y+dy]
            p[-1]=effects(1.0,'left')
# Avoid the USB protection part's vertical VBUS label above its body.
for key2,yy in [('Reference',74.93),('Value',77.47)]:
    p=prop(instances['U5'],key2);one(p,'at')[1:3]=[60.96,yy]
    p[-1]=effects(1.0,'left')
for key2,yy in [('Reference',17.78),('Value',20.32)]:
    one(prop(instances['F2'],key2),'at')[2]=yy
    one(prop(instances['JP2'],key2),'at')[2]=yy
# Use actual component documentation in the output BOM/netlist.
prop(instances['J1'],'Datasheet')[2]='https://gct.co/files/drawings/usb4105.pdf'
prop(instances['U4'],'Datasheet')[2]='https://www.diodes.com/datasheet/download/AP2112.pdf'
prop(instances['F2'],'Datasheet')[2]='https://www.littelfuse.com/assetdocs/littelfuse-ptc-1206l-datasheet?assetguid=2b6a1515-d4ee-4c83-8bd4-152b4901b8f5'

# Every physical pin must be either wired intentionally or explicitly unconnected.
for (ref,p),(_,_,_,typ) in pinmap.items():
    if (ref,p) not in expected and (ref,p) not in nc_expected:
        raise RuntimeError(f'Unassigned pin {ref}.{p} ({typ})')
root.append(node('embedded_fonts',A('no')))
(OUT/'bldc_health.kicad_sch').write_text(dumps(root)+'\n')
(OUT/'BLDC_Health.kicad_sym').write_text(dumps(library)+'\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table\n (lib (name "BLDC_Health")(type "KiCad")(uri "${KIPRJMOD}/BLDC_Health.kicad_sym")(options "")(descr "Verified project symbols"))\n)\n')
(OUT/'fp-lib-table').write_text('(fp_lib_table\n (lib (name "BLDC_Health")(type "KiCad")(uri "${KIPRJMOD}/BLDC_Health.pretty")(options "")(descr "Original IMU footprints, converted to native KiCad"))\n)\n')
project=json.loads((BASE/'bldc_health.kicad_pro').read_text())
project['schematic']['connection_grid_size']=50.0
project['erc']['erc_exclusions']=[]
(OUT/'bldc_health.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
shutil.copyfile(BASE/'bldc_health.kicad_pcb',OUT/'bldc_health.kicad_pcb')
shutil.copytree(BASE/'EASYEDA_MODELS',OUT/'EASYEDA_MODELS',dirs_exist_ok=True)
(OUT/'expected-connections.json').write_text(json.dumps({'nets':{f'{r}.{p}':n for (r,p),n in expected.items()},
                  'no_connect':[f'{r}.{p}' for r,p in sorted(nc_expected)]},indent=2)+'\n')
print(f'Built {len(instances)} symbols with {len(expected)} connected pins in {OUT}')
