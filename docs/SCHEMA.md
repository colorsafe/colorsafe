<!---

ColorSafe: A colorized data storage scheme for archival printing and scanning on paper.

Copyright (C) 2017, Justin Bass

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

-->

# Disclaimer

This schema is a work in progress. The current version is v0.1.0.devX, not yet released for public use.

# Introduction

ColorSafe is a colorized data storage scheme for printing on paper. Its primary use is for reliable long-term archiving of data in the range of bytes to several megabytes, and potentially more. It's aimed for use with standard and widely available printing and scanning devices. Stored appropriately in this way, data can survive virtually indefinitely.

It is heavily inspired by its predecessor, [PaperBak](https://github.com/Rupan/paperbak).

# Definitions

* Original file: The single original data file to be encoded, or retrieved as a result of decoding.
* Encoding: The process of running the original file through the ColorSafe algorithm, outputting an encoded series of image files that can be printed (often a PDF).
* Decoding: The process of running a scanned sequence of ColorSafe encoded data to be processed, outputting the original file and or metadata as accurately as possible.
* Page: A rectangular group of H \* W sectors (typically 10 \* 8), ordered left to right, and then up to down (the way English is read). Each page is associated with a number, which is its order with respect to the original data.
* File data: The data stored by the original file, e.g. the file contents
* File metadata: The metadata associated with the original file, e.g. file size, file name, creation date, etc.
* Header: Each page can have its own plain-text header, typically storing useful metadata for readability and organizational purposes.
* Sector/block: A rectangular group of M \* N dots (typically 64 \* 64), ordered left to right, and then up to down, in little-endian (LSB at the top-left). Each sector is surrounded by a whitespace gap, width G (typically 1), and then a solid black border, width B (typically 1). There are two sector types: data sectors, and metadata sectors.
* Border grid: Each sector's solid black border overlaps with its neighbor. Together, these form a rectangular border grid on each page.
* Dot: The basic unit of ColorSafe data, represented by a number of channels (typically 3: RGB) possibly surrounded by whitepace separating it from its neighbors. The area fraction that the colored portion takes up is represented by F (typically 0.7). Also known as a ColorSafe dot.
* Pixel: The rendered pixel in the encoding output image file. Typically there are many pixels per dot to support whitespace around each dot.
* Printer dot: Unrelated to "dot" or "ColorSafeDot", the smallest unit of printing supported. Used for rendering output for printing.
* Magic row: For purposes of separating the ECC region within each sector or marking the beginning of a metadata sector, a row consisting of bytes that, after XOR, appear as 11001100.
* ECC region: In each sector, there may optionally exist an error-correcting-code region, useful for fixing errors in the data during decoding.
* ECC rate: The effective error-correcting rate, represented by E. For the typical E = 0.2, roughly 20% of all dots, pages, or sectors can be erased - errors with known locations, as in a removal - and the original data will still be recoverable. With unknown locations - as in a smudge or single misread bit - the error correction rate is half E, or 10%.
* Data sector: Each data sector consists of the original data and optional error correction data.
* Metadata sector: Each metadata sector consists of the original file metadata and optional error correction data.

# Scheme

## Encoding scheme

### Valid file sizes

The smallest valid file size is 0-bytes, which will be represented as only metadata. The largest file size is infinite. File sizes must be an integer multiple of bytes.

### Color

Each dot will have a color represented as (R,G,B), with each dot having C bits of color depth and each channel having C / 3 bits. This represents a palette of 2 ^ C colors. Thus there will be C bits of information per dot, with C = 1 corresponding to black and white. Each 8 dots will correspond to C bytes, such that each dot's color-bit Ci corresponds to byte i. The value C must be 1 or a multiple of 3.

As an example, the default for ColorSafe is C = 3, or 1 bit per channel, corresponding to 8 colors (in binary order: black, red, green, yellow, blue, purple, turquoise, white). For every 8 dots, the first dot will have Cr, Cg, Cb corresponding to the first bit in Rbyte, Gbyte, and Bbyte. Thus every 3 bytes of data will correspond to 8 dots.

Higher C values correspond to proportionally higher information density. The best affordable scanners today can reach 48 bits of color depth, or C = 48, but this level of accuracy is unlikely to be reliable due to imprecision, smudging, and aging. Any value over C = 3 will involve bits corresponding to saturation and value, which is more likely to fade inconsistently across pages and sectors as compared to hue, and thus reliability and consistency will drop off vastly after C = 6. In practice C = 3 is a good default, and C = 6 is a good upper limit.

### XOR

As a last step before being written, every byte will unconditionally be masked to avoid long rows or columns of 0's or 1's, which can affect decoding accuracy. The mask is, for even rows (0,2,4, etc.), an XOR with 0x55, alternating 1's and 0's; for odd rows (1,3,5, etc.), it is an XOR with 0xAA, alternating 0's and 1's.

### Ambiguous data

Whenever the original data, ecc data, or metadata contains the magic row anywhere but the last row of the last sector, the file will be encoded ambiguously and with warning, with metadata key "AMB" being inserted if possible.

This case is rare, since most files consider 0-bytes to be a null terminator, and with a large sector-size (M \* N) it will be unlikely to see N/8 0-bytes in a row.

### Padding

If the last data or metadata sector has unused space in the data or ECC regions, it will become 0-padded until the end of the row, and sector.

Most filetypes accept trailing 0's or garbage, so errors in the last sector are unlikely to cause issues with decoding. With a metadata value corresponding to original filesize, these trailing bits can be removed consistently.

### Valid sector sizes

Sector sizes M \* N such that M < 8 or N < 8 are invalid. M and N must be multiples of the byte size, 8. The maximum sector size is infinite, but in practice is typically at most 1024 \* 1024. The minimum size in practice is typically 16 \* 16. The recommended sector size is 64 \* 64.

Larger sector sizes can fit more data, since they have less overhead with borders and gaps. However, larger sector sizes cause damage to be less likely to be detected as an erasure, and may cause overhead for metadata sectors which can often fit into a single 32 \* 32 sector. Very large sectors may also cause less data to fit onto a given page.

## Error-correction code scheme (ECC)

### Definitions

* E: Effective ECC error rate
* Reed-Solomon block length: The entire size of the input string plus ECC data, RSn.
* Reed-Solomon message length: The size of the input string per RS block, RSk.
* Reed-Solomon distance: The approximate maximum number of correctable errors, RSd.

### Description

The requested error-correction rate can be requested to be different for data and metadata sectors. If not, whatever rate is specified will be used for both. The requested rate will correct a combined number of errors (unknown positions) and erasures (errors with known position):

```
E = 2 \* E(errors) + E(erasures)
```

The basic ECC algorithm is a Reed-Solomon code based on E:

```
RSn\_max = 2 ^ 8 - 1 symbols [8 bits per symbol, e.g. max = 255 bytes]
```

```
RSd = RSn - RSk + 1
```

```
RSd ~ E \* RSn
```

If a sector with M \* N / 8 bytes is large enough to require more than one Reed-Solomon block, which are at most 255 bytes, all but the last two RS blocks will be size 255, and the last two RS blocks will equally split the remaining correctable bytes (inequal splits will cause the second-to-last block to be larger than the last). In this way, most RS blocks will be as large as possible, and no RS block will be less than 128 bytes or the maximum that can fit into a sector. These RS blocks will be divided into data and ECC blocks where data blocks will be rounded down and ECC blocks will be rounded up (based on ECC rate).

As an example, for a sector size of 512 \* 512 and ECC = 0.2, the RS blocks will be of sizes:

```
255 [127 times], 160, 159
```

This will correspond to data and ECC block sizes of, respectively:

```
floor( 255 / 1.2 ) [127 times], floor( 160 / 1.2 ), floor ( 159 / 1.2 )
```

```
ceil( 255 - 255 / 1.2 ) [127 times], floor ( 160 - 160 / 1.2 ), floor ( 159 - 159 / 1.2 ) 
```

Thus each ECC bit maps unambiguously to a Reed-Solomon block in the data.

### Unique random permuation

The random permutation for ECC bits will use the Python 2.7 implementation of a Mersenne Twister and shuffle, with seed 0. This is very memory inefficient for large files, but provides excellent error correction compared to other constant memory solutions (such as a quadratic residue number generator).

For multi-page files, the entire ECC region across all pages will need to be decoded and written to memory (or disk) before being usable for error-correcting. Fast verification is possible if a few bits for a given sector are in the sector or page itself, but this is increasingly unlikely with large file sizes.

This position will not be different for metadata and data sectors. Thus, both types of sectors will potentially have error correcting data for the other kind as well.

### Encoding

If error-correction is requested, data and metadata blocks will both be split into two regions, separated by a single magic row. Above the row will be the original data, and below will be the ECC data.

### ECC Rate granularity

Given a sector size M \* N, the ECC rate can only be an integer multiple of vertical side-length less 1:

```
0 / ( N - 1 ), 1 / ( N - 1 ), ..., ( N - 2 ) / ( N - 1 )
```

The user specified ECC rate E will be rounded up to the nearest valid ECC rate possible, or down if larger than (N-2)/(N-1).

### ECC magic rows

For each data and metadata block, the ECC region will not cover the magic row separating the data/metadata from ECC. For each metadata sector, this means the first magic row(s) will be error-corrected, which is redundant buy helpful to maintain consistency with data sectors. This is also necessary since the metadata might be incorrectly damaged to appear like a magic row, which is incorrect.

### ECC rows required

Given E, the desired error correction rate, and M, the height of each sector in dots, the number of ECC rows R required is:

```
( M - 1 ) \* ( 1 - ( 1 / ( 1 + E ) ) )
```

Then the number of data or metadata rows will be M - R - 1.

## Metadata sector

Metadata sectors are an optional feature of ColorSafe, and are hypothetically never required to encode data. However, in practice the decoder will typically rely on values from metadata to vastly speed up decoding and resolve ambiguity. Metadata also helps maintain backwards compatibility by allowing extension of ColorSafe features without changing the entire scheme, e.g. the ECC scheme can be changed by adding an ECC key that corresponds to a value for a different scheme.

### Format

Each metadata sector consists of the following, in order:

1. A single magic row.
2. A padding 5-byte.
3. Color-depth byte: The first byte after the magic row is an integer that determines the number of bits N in all color channels (RGB) on the page. This is always in black or white and not XOR'd, and so up to C = 2 ^ 8 - 1 bits per dot are supported; since this must be a multiple of 3, up to 85 bits per channel are supported. A 0-byte is invalid, implying the current sector is not a metadata sector, or that this is a magic row.
5. Metadata scheme byte: The next three bytes after the color-depth byte are an integer that determines the encoding scheme of that metadata sector's keys and values. This should always be backwards compatible with previous ColorSafe versions. It will be black and white and not XOR'd and so supports up to 2 ^ 24 schemes. For the current version, here is a mapping:
   * 0: Invalid, implying the current sector is not a metadata sector, or the value is damaged.
   * 1: Strings encoded in ASCII, metadata method described in v0.1, all data XOR'd, all int values variable length and little-endian.
6. A padding A-byte.
7. Metadata key-value pairs: The rest of its data will be encoded as any number of key-value pairs: an arbitrary length key string, followed by a single 0-byte, followed by an arbitrary length value string (if value = 0, value will be empty), followed by a single 0-byte (unless it's the last byte of the sector). The value must not have a 0-byte, or it will cause decoding ambiguity. If any custom key appears more than once, then its value will be inserted into a list, and by default ColorSafe will only operate on the first found value.
8. Zero-padding until the end of the metadata sector's data region
9. A magic row
10. ECC data 

Padding 5-bytes (b10101010) and A-bytes (b01010101) around the color-depth bytes and metadata scheme bytes are necessary since those values won't be XOR'd, thus aiding decoding.

If the key-value pair region has less bytes than a pair needs (CRC or TIM, 9 bytes) due to small sector size or high ECC rate, this pair will not be included.

### Standard contents

Metadata will always, if enabled, include the following key-value pairs in order, in each block:

* ECC: ECC mode. If none, will be value 0. 1: ECC with no shuffle (all within same sector). 2: ECC shuffled across current page. 3: ECC shuffled across all pages.
* DAT: Data mode. The mode of encoding and placing data. Default is 1: the standard mode described.
* PAG: Current page number, unsigned int.
* MET: Total number of metadata sectors on the current page, unsigned int.

It will always include the following, in any order and possibly not in every block:

* AMB: Ambiguous encoding. True if included, value ignored. False if not included.
* CRC: A CRC32C (RFC 3720) checksum of the original file. Helps verify decoding quality.
* ECR: ECC rate, an unsigned integer representing rows of ECC data. Helps case where no ECC exists.
* MAJ: Major ColorSafe version, unsigned int. A major version change indicates non-backwards compatibility, such as a change of the location of the color-depth or metadata-scheme bytes.
* MIN: Minor version, unsigned int. A minor version change indicates a backwards compatible feature change, such as adding a metadata scheme or adding functionality to the encoder or decoder.
* REV: Revision version, unsigned int. A revision version change indicates minor backwards compatible changes, such as bug-fixes or functionality-consistent performance improvements.
* SIZ: File size in bytes, unsigned int. Helps clip trailing 0-bytes or garbage. Will always be available by encoder.
* TIM: ColorSafe creation timestamp in seconds since epoch, unsigned int.
* TOT: Total number of pages (0, 1, or not included if 1 page), unsigned int. Will always be available in encoder. Note that the maximum total pages allowed is 2 ^ 64 - 1.

Metadata may include the following key-value pairs where valid:

* EXT: File extension. Optional since non-file may be written.
* NAM: Filename. Will crop to the beginning of filename if too long to fit into a sector. Optional since non-file data may be written.

### Typical metadata size

Typical metadata for a file will be about 100 bytes. Given a 6-byte header in each metadata sector, at least one magic row, 20% error-correction, and usual sector sizes (32x32, 64x64), the metadata should all fit into one or two blocks (not considering the page number, which must be on each page).

### Number of metadata sectors

Each page should have at least 1 metadata block, so that required-ordered metadata are present, most importantly page number. As well, a number of metadata sectors will be added to the file in order to fill the last row. 

The total number of fractional pages is equal to all sectors over the number of sectors per page:

```
totalPages = ( dataSectors + metadataSectors ) / ( sectorsHorizontal * sectorsVertical )
```

Given a minimum number of metadata sectors to just pack the data, the first metadata sector will be on each page, plus the rest across all pages:

```
metadataSectors = totalPages + metadataSectorsMinimum - 1
```

Thus we obtain the simplified equation:

```
totalPages = ceiling ( ( dataSectors + metadataSectorsMinimum - 1 ) / ( sectorsHorizontal * sectorsVertical - 1 ) )
```

With pages known, the metadata sectors add as many sectors as required to fill the last row of the last page. Thus the metadata sector count is an unambiguous result.

Note that if metadata is not included, any data sectors that have no data to fill them will be filled entirely with 0-bytes until the end of the file.

### Positioning

Using Python 2.7's Mersenne Twister and shuffle implementation, each metadata block will be placed across pages using seed 0, and placed within pages using seed equal to page number.

### ECC failing

If ECC fails to correctly decode the metadata, the worst case scenarios are as follows:

* If the color-depth byte is misread in a sector, the decoder will attempt to find the most common color-depth value in every other sector. If the most common value is incorrect, then the entire file will probably be misread. A good decoder implementation will sanity check the file to verify the current color-depth value, or else derive one of its own.
* If the metadata-scheme byte is misread, the entire block may be misread. This will usually cause incorrect key-value pairs, which could cause issues with decoding as described below.
* If the key-value pairs are misread, at worst the entire block may be misread. This could cause correct keys and incorrect values, that may affect decoding. For example, if page number is incorrect, the decoded data will be totally incorrect. If the file size is incorrect (but appears valid, such as correctly implying the data ends in the last sector) the file may be clipped. A good decoder implementation may alleviate these issues.

### Packing algorithm

The metadata will be packed into each sector first-fit decreasing: by sorting the metadata from largest to smallest key-value pair, and inserting each into the first sector that has room. Efficient packing is useful since metadata sectors will be increased to be distributed across all pages; thus inefficient packing would be multiplied greatly.
