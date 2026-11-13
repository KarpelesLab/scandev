// Runs one experiment on nqr_core against a recorded ADC waveform.
//
// stim.hex holds NSHOTS consecutive shots of SHOTLEN samples each; sample 0
// of a shot is the cycle after the sequencer's `sync` (the carrier restart).
// cfg.hex holds the register writes.  The summed capture memory is printed
// as "D <index> <i> <q>" for the Python side to judge.
`timescale 1ns/1ps
module nqr_core_tb;
    parameter SHOTLEN = 16384;
    parameter NSHOTS  = 4;
    parameter NCFG    = 64;

    reg clk = 0;
    always #10 clk = ~clk;          // 50 MHz

    reg         rst = 1;
    reg   [7:0] bus_addr = 0;
    reg  [31:0] bus_wdata = 0;
    reg         bus_we = 0;
    wire [31:0] bus_rdata;
    reg signed [11:0] adc = 0;
    wire tx_en, tx_hi, tx_lo, blank, qdamp, busy;

    nqr_core dut (
        .clk(clk), .rst(rst),
        .bus_addr(bus_addr), .bus_wdata(bus_wdata), .bus_we(bus_we),
        .bus_rdata(bus_rdata), .adc(adc),
        .tx_en(tx_en), .tx_hi(tx_hi), .tx_lo(tx_lo),
        .blank(blank), .qdamp(qdamp), .busy(busy)
    );

    reg [11:0] stim [0:SHOTLEN*NSHOTS-1];
    reg [39:0] cfg  [0:NCFG-1];         // {addr[7:0], data[31:0]}, addr ff = end
    initial $readmemh("stim.hex", stim);
    initial $readmemh("cfg.hex", cfg);

    // ADC model: index restarts at each carrier sync, shot by shot.
    integer k = SHOTLEN;                // parked past the end until first sync
    integer shot_i = -1;
    always @(posedge clk) begin
        if (dut.sync) begin
            k <= 0;
            shot_i <= shot_i + 1;
        end else if (k < SHOTLEN) begin
            adc <= stim[shot_i * SHOTLEN + k];
            k <= k + 1;
        end else
            adc <= 0;
    end

    // Transmit bookkeeping: cycles with the amplifier on, and a check that
    // the two switches are never on together.
    integer tx_cycles = 0, hi_cycles = 0, tx_edges = 0;
    reg hi_d = 0;
    always @(posedge clk) begin
        if (tx_en) tx_cycles <= tx_cycles + 1;
        if (tx_hi) hi_cycles <= hi_cycles + 1;
        if (tx_hi && !hi_d) tx_edges <= tx_edges + 1;
        hi_d <= tx_hi;
        if (tx_hi && tx_lo) begin
            $display("FAIL shoot-through");
            $finish;
        end
    end

    task wr(input [7:0] a, input [31:0] d);
        begin
            @(posedge clk); bus_addr <= a; bus_wdata <= d; bus_we <= 1;
            @(posedge clk); bus_we <= 0;
        end
    endtask

    task rd(input [7:0] a, output [31:0] d);
        begin
            @(posedge clk); bus_addr <= a;
            @(posedge clk); @(posedge clk); d = bus_rdata;
        end
    endtask

    integer n, nsamp;
    reg [31:0] v, vi, vq;
    reg [39:0] cw;
    initial begin
        repeat (4) @(posedge clk);
        rst <= 0;
        rd(8'h0c, v);
        $display("ID %h", v);
        n = 0;
        cw = cfg[0];
        while (cw[39:32] != 8'hff) begin
            wr(cw[39:32], cw[31:0]);
            n = n + 1;
            cw = cfg[n];
        end
        wr(8'h00, 32'h3);               // clear + start
        @(posedge clk);
        while (busy) @(posedge clk);
        rd(8'h00, v);
        $display("SHOTS %0d", v[31:16]);
        rd(8'h0b, v);
        nsamp = v;
        $display("NSAMP %0d", nsamp);
        $display("TX %0d %0d %0d", tx_cycles, hi_cycles, tx_edges);
        for (n = 0; n < nsamp; n = n + 1) begin
            wr(8'h08, n);
            rd(8'h09, vi);
            rd(8'h0a, vq);
            $display("D %0d %0d %0d", n, $signed(vi), $signed(vq));
        end
        $finish;
    end
endmodule
