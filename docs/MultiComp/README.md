MISTer MultiComp 
================

Port of Grant Searle's MultiComp to the MiSTer. 

Ported by Cyril Venditti and Fred VanEijk.

Updated by S0urceror to use MiSTer image files, use all 4 machine types and have the MiSTer 
UART connected to serial interface 2 of the core. The latter allows to use the core remotely.

Here's a cleaned-up and more organized version of the information:

## Using the MiSTer Serial Terminal/Console

### Connection Methods:
1. USB: Connect the console port from the MiSTer FPGA to your computer using a USB cable.
2. Network: Use SSH to connect to the MiSTer FPGA if you have a Wireless or Ethernet connection.

### Setting Up the Connection:

#### For UART/Serial with PuTTY:
- Connect at 115200 baud, 8 bits, no parity to the COM port#### 
#### For SSH with PuTTY:
- Connect to the ip address of your MISTer fpga

#### Linux command line to establish the connection to the core:

1. Identify the UART device:
   - Usually mapped to `/dev/ttyS1` or `/dev/ttyUSB0`
   - Use this command to help identify the correct device:
     ```
     dmesg | grep tty
     ```

2. Access the serial terminal:
   - Use `screen` or `minicom`
   - Example command with `screen`:
     ```
     screen /dev/ttyS1 115200
     ```
   - Replace `/dev/ttyS1` with the correct device identifier
   - Change 115200 to the appropriate baud rate if different

### Additional Information:
For more details on console connection, refer to the official MiSTer documentation:
[MiSTer Console Connection Guide](https://mister-devel.github.io/MkDocs_MiSTer/advanced/console/)



## The MiSTer OSD allows the access to four machines:

### Z80 CP/M: 
You can now use both an external SDCard and/or select the image file within MiSTer. Whatever you like.

For convenience you can use the Multicomp FPGA - CP/M Demo Disk from Obsolescence Guaranteed:
http://obsolescence.wixsite.com/obsolescence/multicomp-fpga-cpm-demo-disk

After you have flashed the CP/M Demo Disk to the SD Card you will have to use the secondary SD Card on the MiSTer on the I/O Board:
https://github.com/MiSTer-devel/Wiki_MiSTer/wiki/IO-Board

Using CP/M - from Grant Searle website:
http://searle.x10host.com/Multicomp/cpm/fpgaCPM.html

### Z80 Basic:
SGN, INT, ABS ,USR, FRE, INP, POS, SQR, RND ,LOG, EXP, COS, SIN, TAN, ATN, PEEK ,DEEK ,LEN, STR$, VAL ,ASC, CHR$ ,LEFT$, 
RIGHT$, MID$, END, FOR, NEXT, DATA, INPUT, DIM, READ, LET, GOTO, RUN, IF, RESTORE, GOSUB, RETURN, REM, STOP, OUT, ON, 
NULL, WAIT,  DEF, POKE, DOKE, LINES, CLS, WIDTH, MONITOR, PRINT, CONT, LIST, CLEAR, NEW, TAB, TO, FN, SPC, THEN, NOT, 
STEP, +, -, *, /, ^, AND, OR, >, <, = 

PLUS my additional implementations here (making it version 4.7b):

HEX$(nn) - convert a SIGNED integer (-32768 to +32767) to a string containing the hex value
BIN$(nn) - convert a SIGNED integer (-32768 to +32767) to a string containing the binary value
&Hnn - interpret the value after the &H as a HEX value (signed 16 bit)
&Bnn - interpret the value after the &B as a BINARY value (signed 16 bit)

### 6502 Basic - No SD card support (No CSAVE/CLOAD):
END, FOR, NEXT, DATA, INPUT, DIM, READ, LET, GOTO, RUN, IF, RESTORE, GOSUB, RETURN, REM, STOP, ON, NULL, WAIT, DEF, POKE, PRINT,
CONT, LIST, CLEAR, NEW, TAB(, TO, FN, SPC(, THEN, NOT, STEP, SGN, INT, ABS, USR, FRE, POS, SQR, RND, LOG, EXP, COS, SIN, TAN, ATN,
PEEK, LEN, STR$, VAL, ASC, CHR$, LEFT$, RIGHT$, MID$, +, -, *, /, ^, AND, OR, >, +, <

### 6809 Basic - No SD card support(No CSAVE/CLOAD):
FOR, GO, REM, ELSE, IF, DATA, PRINT, ON GOSUB, ON GOTO, INPUT, LINE INPUT, END, NEXT, DIM, READ, RUN, RESTORE, RETURN, STOP, POKE,
CONT, LIST, CLEAR, NEW, EXEC, TAB, TO, SUB, THEN, NOT, STEP, +, -, *, /, ^, AND, OR, >, =, <, DEL, DEF, LET, RENUM, FN, &, &H, TRON,
TROFF, EDIT, SGN, INT, ABS, USR, RND, SIN, PEEK, LEN, STR$, VAL, ASC, CHR$, LEFT$, RIGHT$, MID$, INKEY$, MEM, ATN, COS, TAN, EXP, FIX,
LOG, SQR, HEX$, VARPTR, INSTR, STRING$, MID$ (MODIFICATION), POS

http://searle.x10host.com/Multicomp/#BASICKeywords

### License

__Software and VHDL project download link__

By downloading these files you must agree to the following: The original
copyright owners of ROM contents are respectfully acknowledged.  Use of the
contents of any file within your own projects is permitted freely, but any
publishing of material containing whole or part of any file distributed
here, or derived from the work that I have done here will contain an
acknowledgment back to myself, Grant Searle, and a link back to this page.
Any file published or distributed that contains all or part of any file
arom this page must be made available free of charge.

### Original Author
Grant Searle

### URL
[Grant's MULTICOMP pick and mix computer](http://searle.x10host.com/Multicomp/)

### Note
The 6809 Basic is not resetting  properly. This issue is present in the original Grant Searle's MultiComp project
