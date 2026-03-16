# Coglet
Will Cogley's DIY Desktop Companion for Makers

# Instructions
Refer to the build video below. For further reading, refer to the translated docs for how to upload to the ESP.



[<img src="https://img.youtube.com/vi/-7I-jFSNP2E/hqdefault.jpg" width="600" height="300"
/>]([https://www.youtube.com/watch?v=-7I-jFSNP2E)


# Known Issues
PCB (CogNog V1.0):
- USB socket for RP2040 is tight - requires a slim USB-C cable
- ESP Camera socket too close to other components
- In general needs more bulk capacitance to manage power dips
- Mic socket too close to ESP
- Camera will not work with default pins and simultaneously use tasks requiring PSRAM - must rewire the following ESP pins and use camera-version branch of CogletESP
- 35->14
- 36->41
- 37->42
- Mouth pin is on pin 19 - the final slot - which is unintuitive
- Camera feed for ESP32 Cam is horizontally flipped!
  
Mechanical
- Servos are too tight generally - we are working on finding a better servo supplier
- There are some sub-optimal snap-fits which will be converted to use screws at some point
- On lower quality PLA the servos can lose grip by stripping away the plastic

# Parts List
Consider backing our kickstarter so we can provide all the parts in one place!
- CogNog PCB - See project files
- [Grove Vision AI V2 plus camera and adaptor](https://nmrobots.com/products/grove-vision-ai-module-v2-hd-camera-adaptor-15-pin-flex-cable)
- [Microphone](https://www.amazon.co.uk/EC-Buying-INMP441-Omnidirectional-Microphone/dp/B0C1C64R8S/ref=sr_1_24?crid=QYJZSFNCQO8X&dib=eyJ2IjoiMSJ9.lZlZ1cPnrTgMcv-W-gCN1fLz9EHti-quOgiDx0rtgG0M9T7hHUXFiX9OIZak1dpRXu---l3GiSeW8R92Z_h_xxpwWeot2r3mSNT7EdTnE8b72qqrtV5jpGvTfk94t-D-bhzV9SKtaXPmQh1oV27CHmToelQJInbJ8K1nIVu62k7QtNYLLVGJzOr-KHE9oqe8AwE7JJfAy0MUWYFivl2qMgDdEnIWL8ARlwTEV-TnNDOQzvP9WgYwM82FW8ZkRyjkoJeUmunKjfBcSE-evoIkI6TtszoGN2k4I_8tNI02TN4.wUYZ98wtWVpGQZSIVSkuclgJsP47m4mCmyZ86vnJiZk&dib_tag=se&keywords=esp+microphone&qid=1773668375&sprefix=espmicrophone%2Caps%2C317&sr=8-24)
- [6 Pin PicoBlade Connector](https://thepihut.com/products/1-25mm-pitch-6-pin-cable-20cm-long-1-1-cable-molex-picoblade-compatible)
- [Speaker](https://www.aliexpress.com/item/1005008267342362.html?spm=a2g0o.order_list.order_list_main.5.2c9d1802tZvBqq)
- USB input to JST XH (3A recommended)
- [ESP Camera - OV3660](https://www.aliexpress.com/item/1005007456084280.html?spm=a2g0o.productlist.main.37.1c1764cexl9Lvj&utparam-url=scene%3Asearch%7Cquery_from%3Apc_back_same_best%7Cx_object_id%3A1005007456084280%7C_p_origin_prod%3A&algo_pvid=5fbe8195-0505-46c8-8a90-e575b8ea193c&algo_exp_id=5fbe8195-0505-46c8-8a90-e575b8ea193c&pdp_ext_f=%7B%22order%22%3A%222535%22%2C%22fromPage%22%3A%22search%22%7D&pdp_npi=6%40dis%21GBP%2115.19%213.54%21%21%21134.90%2131.43%21%402103864c17736782410096615ee2dd%2112000040830794856%21sea%21UK%210%21ABX%211%210%21n_tag%3A-29910%3Bd%3A68e21fdb%3Bm03_new_user%3A-29895%3BpisId%3A5000000197851867)
- [ESP Cam Ribbon Cable](https://www.digikey.co.uk/en/products/detail/gct/05-24-A-0152-A-4-06-4-T/21266890)
- [ESP Cam Adaptor](https://www.digikey.co.uk/en/products/detail/adafruit-industries-llc/4524/12323567?s=N4IgTCBcDaIIwFYwA4C0AWJ7UDsAmIAugL5A)
- [9x Servos - These are tight, MG90s may also work](https://uk.robotshop.com/products/kpower-9g-analog-metal-gear-rc-servo-m0090)
- [Realistic Camera-Compatible Eyes](https://nmrobots.com/products/ultra-realistic-eyeball-compatible-with-face-tracking-eyemech-%CE%B53-4)
