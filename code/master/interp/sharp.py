import subprocess, sys, numpy as np, cv2
W,H=1920,1080
SC=[('fadein',30),('intro',158),('backdown',69),('fadeaway',43),('rim',24),('celebrate',36),('newspaper',55),('fastcuts',209),('alleyoop',71),('fadeout',68),('jersey',21),('profile',118)]
def lap(p):
    pr=subprocess.Popen(['ffmpeg','-v','error','-i',p,'-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
    out=[]
    while True:
        b=pr.stdout.read(W*H)
        if len(b)<W*H: break
        g=np.frombuffer(b,np.uint8).reshape(H,W)
        out.append(cv2.Laplacian(g,cv2.CV_32F).var())
    return np.array(out)
a=lap(sys.argv[1]); b=lap(sys.argv[2])
print(len(a),len(b))
i=0
print(f"{'scene':10s} {'30fps':>7s} {'60 real':>8s} {'60 rife':>8s} {'rife/real':>9s} {'worst rife frame':>16s}")
for n,k in SC:
    s30=a[i:i+k].mean(); ev=b[2*i:2*i+2*k:2]; od=b[2*i+1:2*i+2*k:2]
    r=od/np.maximum(ev,1e-3)
    w=int(np.argmin(r))
    print(f"{n:10s} {s30:7.0f} {ev.mean():8.0f} {od.mean():8.0f} {od.mean()/ev.mean():9.2f}   {r[w]:.2f} at {(i+w)/30:.2f}s")
    i+=k
