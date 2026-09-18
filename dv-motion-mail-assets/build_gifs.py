import json, os, math
from PIL import Image, ImageDraw, ImageFont

ROOT=os.path.dirname(__file__)
OUT=os.path.join(ROOT,"gifs")
os.makedirs(OUT,exist_ok=True)

def font(sz,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p,sz)

def hexrgb(h):
    h=h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def mix(a,b,t):
    return tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3))

def rounded(draw,box,r,fill,outline=None,w=1):
    draw.rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=w)

with open(os.path.join(ROOT,"specs.json"),"r",encoding="utf-8") as f:
    specs=json.load(f)

for s in specs:
    W,H=600,300
    dark=hexrgb(s["dark"]); accent=hexrgb(s["accent"]); accent2=hexrgb(s["accent2"]); bg=hexrgb(s["bg"])
    frames=[]
    total=24
    for k in range(total):
        t=k/total
        im=Image.new("RGB",(W,H),bg)
        d=ImageDraw.Draw(im)
        # header
        d.rectangle((0,0,W,74),fill=dark)
        d.rectangle((0,0,W,7),fill=accent)
        d.text((24,18),"DV LABS  •  MOTION IDEAL ALPHA",font=font(13,True),fill=accent)
        title=s["name"]
        if len(title)>36: title=title[:35]+"…"
        d.text((24,42),title,font=font(23,True),fill=(255,255,255))

        # animated orbital motif
        cx,cy=530,38
        for j,r in enumerate((12,21,31)):
            ang=2*math.pi*(t*(1+j*.17)+j*.21)
            x=cx+math.cos(ang)*r
            y=cy+math.sin(ang)*r
            col=accent if j%2==0 else accent2
            d.ellipse((x-4,y-4,x+4,y+4),fill=col)
        d.ellipse((cx-5,cy-5,cx+5,cy+5),fill=accent2)

        # path rail
        d.text((24,92),s["headline"],font=font(15,True),fill=dark)
        steps=s["steps"][:3]
        xs=[28,218,408]
        for i,(x,label) in enumerate(zip(xs,steps)):
            phase=(t*3-i)%3
            glow=max(0,1-abs(phase-1))
            base=accent if i%2==0 else accent2
            fill=mix((245,247,250),base,0.22+0.58*glow)
            outline=mix((180,190,200),base,0.4+0.6*glow)
            rounded(d,(x,130,x+164,210),18,fill,outline,3)
            d.text((x+14,145),f"0{i+1}",font=font(12,True),fill=outline)
            # two-line label
            words=label.split()
            line1=""; line2=""
            for w0 in words:
                if len(line1+" "+w0)<=17 and not line2:
                    line1=(line1+" "+w0).strip()
                else:
                    line2=(line2+" "+w0).strip()
            d.text((x+14,168),line1,font=font(15,True),fill=dark)
            if line2: d.text((x+14,188),line2[:20],font=font(13,True),fill=dark)

        # moving progress bar
        d.rounded_rectangle((24,232,576,244),radius=6,fill=(220,226,232))
        prog=int(24+(552*((math.sin(2*math.pi*t-math.pi/2)+1)/2)))
        d.rounded_rectangle((24,232,prog,244),radius=6,fill=accent)
        # value pill pulse
        pulse=(math.sin(2*math.pi*t)+1)/2
        pill=mix(dark,accent2,0.22*pulse)
        rounded(d,(24,258,576,286),14,pill)
        d.text((38,264),s["value"],font=font(12,True),fill=(255,255,255))
        frames.append(im.quantize(colors=128,method=Image.Quantize.MEDIANCUT))

    path=os.path.join(OUT,s["slug"]+".gif")
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=85,loop=0,optimize=True,disposal=2)
    print(path)
