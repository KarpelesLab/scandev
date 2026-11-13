// nqr_core -- the spectrometer without its host link or its pins.
//
// A register bus programs the carrier, the pulse table and the receiver;
// `start` runs the table `nshots` times and the capture memory ends up
// holding the sum of all shots, which the host reads back.
//
//   0x00 w  CTRL     bit0 start, bit1 clear (next run overwrites the memory)
//        r  STATUS   bit0 busy, [31:16] shots completed
//   0x01 rw FREQ     carrier, f = FREQ * f_clk / 2^32
//   0x02 rw DECIM    receiver decimation R, 2..1024
//   0x03 rw SHIFT    receiver output right shift, 0..53
//   0x04 rw NSHOTS   shots per run
//   0x05 rw PADDR    pulse table address, 0..63
//   0x06 rw PDUR     step duration in clock cycles (>= 2)
//   0x07 w  PCTRL    step control byte; writing stores {PCTRL, PDUR} at PADDR
//   0x08 rw RADDR    capture read address
//   0x09 r  RDI      summed I at RADDR
//   0x0a r  RDQ      summed Q at RADDR
//   0x0b r  NSAMP    samples captured per shot
//   0x0c r  ID       0x4e515231 ("NQR1")
module nqr_core (
    input  wire               clk,
    input  wire               rst,

    input  wire         [7:0] bus_addr,
    input  wire        [31:0] bus_wdata,
    input  wire               bus_we,
    output reg         [31:0] bus_rdata,

    input  wire signed [11:0] adc,

    output wire               tx_en,
    output wire               tx_hi,     // high-side switch on
    output wire               tx_lo,     // low-side switch on
    output wire               blank,
    output wire               qdamp,
    output wire               busy
);
    reg [31:0] r_freq;
    reg [10:0] r_decim;
    reg  [5:0] r_shift;
    reg [15:0] r_nshots;
    reg  [5:0] r_paddr;
    reg [31:0] r_pdur;
    reg [10:0] r_raddr;

    wire w_ctrl  = bus_we && bus_addr == 8'h00;
    wire w_pctrl = bus_we && bus_addr == 8'h07;
    wire start   = w_ctrl && bus_wdata[0];
    wire clear   = w_ctrl && bus_wdata[1];

    always @(posedge clk) begin
        if (rst) begin
            r_freq   <= 32'd0;
            r_decim  <= 11'd50;
            r_shift  <= 6'd0;
            r_nshots <= 16'd1;
            r_paddr  <= 6'd0;
            r_pdur   <= 32'd2;
            r_raddr  <= 11'd0;
        end else if (bus_we) case (bus_addr)
            8'h01: r_freq   <= bus_wdata;
            8'h02: r_decim  <= bus_wdata[10:0];
            8'h03: r_shift  <= bus_wdata[5:0];
            8'h04: r_nshots <= bus_wdata[15:0];
            8'h05: r_paddr  <= bus_wdata[5:0];
            8'h06: r_pdur   <= bus_wdata;
            8'h08: r_raddr  <= bus_wdata[10:0];
            default: ;
        endcase
    end

    // Power-up values, the same as reset: the carrier runs from the first
    // clock edge, before reset has had a cycle to act.
    initial begin
        r_freq = 32'd0; r_decim = 11'd50; r_shift = 6'd0; r_nshots = 16'd1;
        r_paddr = 6'd0; r_pdur = 32'd2; r_raddr = 11'd0; bus_rdata = 32'd0;
    end

    wire        acquire, sync, shot_start;
    wire  [1:0] tx_quad;
    wire [15:0] shot;

    pulse_seq u_seq (
        .clk(clk), .rst(rst),
        .prog_we(w_pctrl), .prog_addr(r_paddr),
        .prog_data({bus_wdata[7:0], r_pdur}),
        .start(start && !busy), .nshots(r_nshots),
        .busy(busy), .shot(shot), .shot_start(shot_start),
        .tx_en(tx_en), .tx_quad(tx_quad), .blank(blank), .qdamp(qdamp),
        .acquire(acquire), .sync(sync)
    );

    wire        [31:0] phase;
    wire signed [11:0] lo_sin, lo_cos;

    nco u_nco (
        .clk(clk), .sync(sync), .freq(r_freq),
        .phase(phase), .sin(lo_sin), .cos(lo_cos)
    );

    // Square-wave drive for a switching amplifier, in phase with sin().
    wire [1:0] tx_top = phase[31:30] + tx_quad;
    assign tx_hi = tx_en & ~tx_top[1];
    assign tx_lo = tx_en &  tx_top[1];

    wire signed [31:0] d_i, d_q;
    wire               d_valid;

    ddc u_ddc (
        .clk(clk), .sync(sync), .adc(adc),
        .lo_sin(lo_sin), .lo_cos(lo_cos),
        .decim(r_decim), .shift(r_shift),
        .i(d_i), .q(d_q), .valid(d_valid)
    );

    wire        [11:0] n_samp;
    wire signed [31:0] rd_i, rd_q;

    capture #(.AW(11)) u_cap (
        .clk(clk), .rst(rst), .clear(clear), .shot_start(shot_start),
        .acquire(acquire), .valid(d_valid), .i(d_i), .q(d_q),
        .count(n_samp),
        .rd_addr(r_raddr), .rd_i(rd_i), .rd_q(rd_q)
    );

    always @(posedge clk) begin
        case (bus_addr)
            8'h00:   bus_rdata <= {shot, 15'd0, busy};
            8'h01:   bus_rdata <= r_freq;
            8'h02:   bus_rdata <= {21'd0, r_decim};
            8'h03:   bus_rdata <= {26'd0, r_shift};
            8'h04:   bus_rdata <= {16'd0, r_nshots};
            8'h05:   bus_rdata <= {26'd0, r_paddr};
            8'h06:   bus_rdata <= r_pdur;
            8'h08:   bus_rdata <= {21'd0, r_raddr};
            8'h09:   bus_rdata <= rd_i;
            8'h0a:   bus_rdata <= rd_q;
            8'h0b:   bus_rdata <= {20'd0, n_samp};
            8'h0c:   bus_rdata <= 32'h4e515231;
            default: bus_rdata <= 32'd0;
        endcase
    end
endmodule
