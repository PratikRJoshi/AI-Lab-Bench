# Truth Analysis: How Apple AirTag Works
**Source**: Direct image upload (infographic by Neo Kim)
**Analyzed**: 2026-04-13
**Content type**: General Science (Technology / Cryptography)
**Format**: Image Post (single infographic)

**Share?**: Yes, with minor caveats — the overall architecture is correct and well-explained for a general audience. Two claims have small inaccuracies (key rotation timing and the "location sending" framing), but the fundamental mental model it builds is sound.

## Summary

A 10-step infographic explaining how Apple AirTags locate lost items using Bluetooth Low Energy, public-key cryptography, and Apple's crowdsourced Find My network. The explanation walks through hardware, key generation, broadcasting, crowd-relaying, encryption, and owner decryption.

## Analysis

### Claim Validation

**Claim 1: "An AirTag contains a low-power CPU and a tiny amount of memory."**
**Supported.** The original AirTag uses a Nordic Semiconductor nRF52832 SoC: ARM Cortex-M4F @ 64 MHz, 64 KB RAM, 512 KB flash. The V2 AirTag (Jan 2026) upgrades to the nRF52840. Both are low-power BLE-class microcontrollers. "Tiny amount of memory" is accurate — 64 KB RAM is orders of magnitude smaller than a smartphone.

**Claim 2: "A public-private key pair gets created when a user adds an AirTag."**
**Supported.** Apple's Find My security documentation confirms that during pairing, the AirTag and the owner's device establish a shared secret and generate an initial NIST P-224 elliptic curve key pair. The private key is stored in iCloud Keychain; the AirTag derives rotating public keys from the shared secret.

**Claim 3: "The AirTag doesn't use GPS or WiFi for communication; instead, it uses Bluetooth Low Energy."**
**Supported.** AirTags have no GPS receiver and no WiFi radio. The only wireless interfaces are BLE 5.0, UWB (Apple U1 chip), and a passive NFC-A tag. All location data comes from other devices' GPS — never from the AirTag itself.

**Claim 4: "They send AirTag's location, which is near its owner's iPhone, using Bluetooth or Ultra Wideband."**
**Partially misleading.** The AirTag does not "send its location." It has no GPS and does not know where it is. It broadcasts a BLE identifier; nearby Apple devices determine *their own* location and associate it with the AirTag's broadcast. UWB (Precision Finding) is used for close-range directional finding between the owner's device and the AirTag — it is not used for the crowd-relay location mechanism. The infographic conflates two different functions: (a) the crowd-sourced location relay (BLE only) and (b) the owner's Precision Finding (UWB, short-range).

**Claim 5: "Bluetooth and Ultra Wideband communication won't work if the owner's iPhone is far away from the AirTag."**
**Supported.** BLE range is ~30–100 feet depending on obstacles. UWB Precision Finding requires the owner's iPhone to be within ~15 meters. This is the correct setup for why the crowd-relay network is needed.

**Claim 6: "AirTag broadcasts its public key every 2 seconds over Bluetooth."**
**Mostly supported, with a nuance.** Reverse engineering confirms AirTags transmit BLE advertisements every ~2 seconds when separated from the owner — this is accurate. However, it is not the *public key* that is broadcast raw. The AirTag broadcasts a rotating 128-bit BLE advertisement derived from the public key. The actual P-224 public key rotates approximately every 15 minutes (with the full key rotating daily at 04:00). The "every 2 seconds" refers to the BLE advertisement interval, not the key rotation interval.

**Claim 7: "Someone else's iPhone, which is nearby, receives the broadcast signal."**
**Supported.** Any Apple device (iPhone, iPad, Mac) participating in the Find My network (~2 billion devices) can receive these BLE advertisements. This happens transparently in the background without the relay device's owner knowing.

**Claim 8: "The iPhone encrypts its location data and timestamp using the received public key."**
**Supported.** The relay device takes its own GPS coordinates and a timestamp, encrypts them using the AirTag's broadcast public key (ECIES on P-224), and packages this as an encrypted location report. Only the corresponding private key holder can decrypt it.

**Claim 9: "The iPhone uploads the encrypted data to the Apple server over HTTPS."**
**Supported.** Encrypted location reports are uploaded to Apple's servers. Apple acts as a blind relay — it stores the ciphertext but cannot decrypt it because it does not possess the owner's private key.

**Claim 10: "The owner then decrypts the received location data using the private key."**
**Supported.** The owner's device downloads encrypted reports from Apple's server, uses the private key (synced via iCloud Keychain across their devices) to decrypt, and displays the AirTag's location on a map.

### Visual Analysis

The infographic uses a clean, numbered list format with highlighted key terms. No misleading visual techniques — no graphs, no statistics, no emotional appeals. The book-page aesthetic adds a sense of authority but is purely stylistic. The presentation is straightforward and educational.

### Summary of Accuracy

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Low-power CPU, tiny memory | Supported |
| 2 | Key pair created on setup | Supported |
| 3 | No GPS or WiFi, uses BLE | Supported |
| 4 | Sends location via BT/UWB | Partially misleading |
| 5 | No long-range communication | Supported |
| 6 | Broadcasts public key every 2s | Mostly supported (nuanced) |
| 7 | Nearby iPhone receives signal | Supported |
| 8 | Encrypts location with public key | Supported |
| 9 | Uploads to Apple over HTTPS | Supported |
| 10 | Owner decrypts with private key | Supported |

## Evidence / Validation Links

- Apple Support. "Find My security." Apple Platform Security Guide. https://support.apple.com/guide/security/find-my-security-sec6cbc80fd0/web
- Apple Newsroom. "Apple introduces new AirTag with expanded range and improved findability." Jan 2026. https://www.apple.com/newsroom/2026/01/apple-introduces-new-airtag-with-expanded-range-and-improved-findability/
- Catley, Adam. "AirTag Reverse Engineering." https://adamcatley.com/AirTag.html — Confirms 2-second BLE advertisement interval and daily key rotation at 04:00.
- Heinrich, A., et al. "Who Can Find My Devices? Security and Privacy of Apple's Crowd-Sourced Bluetooth Location Tracking System." Proceedings on Privacy Enhancing Technologies, 2023. https://petsymposium.org/popets/2023/popets-2023-0102.pdf
- EDN. "Teardown: Apple AirTag." https://www.edn.com/teardown-apple-airtag/ — Hardware specifications of nRF52832 SoC.

## Verdict

The infographic is a solid, mostly accurate high-level explainer of AirTag architecture. Eight of ten claims are fully supported by Apple's documentation and independent reverse engineering. Claim 4 is the weakest — it says the AirTag "sends its location," when in reality the AirTag has no idea where it is; nearby devices supply the location. Claim 6 conflates the BLE advertisement interval (2 seconds, correct) with key rotation (actually every 15 minutes). These are minor pedagogical simplifications, not fundamental errors. The core mental model — BLE broadcast → crowd relay → encrypted upload → owner decryption — is correct.

## ELI5 — Friend to Friend

Yeah, this is legit. It's a solid explanation of how AirTags work — the big picture is right. Two small nitpicks: the AirTag doesn't actually know where it is (it has no GPS), so saying it "sends its location" is a bit misleading — really, other people's iPhones figure out where the AirTag is. And the "broadcasts its public key every 2 seconds" thing — it broadcasts a *signal* every 2 seconds, but the actual key rotates every 15 minutes. But honestly? For a quick explainer, this nails it. Thumbs up.
