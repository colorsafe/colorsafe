# To Do

General changes to encoding:

- The solid grid and gaps could potentially be replaced by special symbols where the grid lines meet, similar to QR codes and Optar. Assuming that decoding accuracy is roughly the same, we could fit in sector-local ECC bits where the border and gap were (each border of ECC bits correcting the half of the sector nearest to it, and directly between the symbols could be a timing pattern), without changing the simple sector scheme already in place. This could also be optional, as part of a different data encoding mode.
- An optional encoding feature could fill remaining page space with extra ECC bits (rather than metadata sectors). Extra ECC improves metadata redundancy indirectly.
- Metadata can be arbitrary length if we use a multipart key: NAM0, NAM1, NAM2, ... NAMT (total number of NAM keys).
- Add a shade byte to metadata header, right after color depth.
- The XOR mask could be changed by the data encoding mode to nearly eliminate the possibility of ambiguous encoding (data with an unintentional first magic row in any sector can be modified by trying other XOR schemes). A different mask can also optimize data to be as readable as possible (no too-dark or too-light sectors). If the mask is only applied to data sectors, then this could be driven by a metadata key-pair rather than metadata header. 
- All ambiguous sectors should have their sector number marked in another metadata sector, rather than the file being marked as ambiguous without knowledge of the affected locations.
- Eventually, predefined file-types could be supported with well-defined metadata parameters. Future-proof image and audio could be created by converting from common standard types.  
- A future-proof optional data compression and encryption scheme should be supported eventually.
- Each metadata block should have a small CRC value regarding its important header information to avoid it being read incorrectly. If it's incorrect, technically we cannot unambiguously correct it, since we need to read it first to know the data, ECC, and metadata schemes unambiguously.
- The first block on any page should be a metadata block, to improve decoding for the common case. Random reproducible can be applied to subsequent blocks. But without local ECC or CRC, reading the metadata block will not improve speed. 
- Magic row can technically be configurable, assuming ECC rows are preceded by the same magic row, and there are a sufficient number of sectors to infer it - or if we use the first metadata sector's first row (could be flaky).
