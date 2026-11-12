// Minimal MD5 for tests (RFC 1321), exposes a CryptoJS-like API used by the page.
(function(){
function md5bytes(bytes){
  const K=new Uint32Array(64), S=[7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21];
  for(let i=0;i<64;i++)K[i]=Math.floor(Math.abs(Math.sin(i+1))*2**32)>>>0;
  const len=bytes.length, nb=((len+8)>>>6)+1, w=new Uint32Array(nb*16);
  for(let i=0;i<len;i++)w[i>>2]|=bytes[i]<<((i%4)*8);
  w[len>>2]|=0x80<<((len%4)*8);
  w[nb*16-2]=(len*8)>>>0; w[nb*16-1]=Math.floor(len/536870912)>>>0;
  let a0=0x67452301,b0=0xefcdab89,c0=0x98badcfe,d0=0x10325476;
  for(let j=0;j<nb*16;j+=16){
    let A=a0,B=b0,C=c0,D=d0;
    for(let i=0;i<64;i++){
      let F,g;
      if(i<16){F=(B&C)|(~B&D);g=i;}else if(i<32){F=(D&B)|(~D&C);g=(5*i+1)%16;}
      else if(i<48){F=B^C^D;g=(3*i+5)%16;}else{F=C^(B|~D);g=(7*i)%16;}
      F=(F+A+K[i]+w[j+g])>>>0; A=D; D=C; C=B; B=(B+((F<<S[i])|(F>>>(32-S[i]))))>>>0;
    }
    a0=(a0+A)>>>0;b0=(b0+B)>>>0;c0=(c0+C)>>>0;d0=(d0+D)>>>0;
  }
  return [a0,b0,c0,d0].map(v=>[0,8,16,24].map(s=>((v>>>s)&255).toString(16).padStart(2,'0')).join('')).join('');
}
window.CryptoJS={lib:{WordArray:{create:(u8)=>({u8})}},MD5:(wa)=>({toString:()=>md5bytes(wa.u8)})};
})();
