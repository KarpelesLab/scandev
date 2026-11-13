// ddc -- digital down-converter: mix to baseband, 3-stage CIC decimator.
//
//   i + jq = CIC( adc * exp(-j * phase) )
//
// `sync` restarts the decimation counter so the output sample grid sits at
// the same place in every shot.  The integrators are never cleared: they are
// modular arithmetic and the combs take differences, so their absolute value
// does not matter.
//
// Gain from an input sine of amplitude A (LSB) at the carrier:
//   A * 2047/2 * R^3 / 2^shift
// Widths: 24-bit product + 3*log2(1024) = 54 bits, so R may be 2..1024.
module ddc (
    input  wire               clk,
    input  wire               sync,
    input  wire signed [11:0] adc,
    input  wire signed [11:0] lo_sin,   // from nco, aligned with each other
    input  wire signed [11:0] lo_cos,
    input  wire        [10:0] decim,    // R, 2..1024
    input  wire         [5:0] shift,    // right shift applied to the output
    output reg  signed [31:0] i,
    output reg  signed [31:0] q,
    output reg                valid
);
    localparam W = 54;

    reg signed [23:0] mi, mq;
    always @(posedge clk) begin
        mi <= adc * lo_cos;
        mq <= -(adc * lo_sin);
    end

    // integrators, at the input rate
    reg signed [W-1:0] ii1, ii2, ii3, qi1, qi2, qi3;
    always @(posedge clk) begin
        ii1 <= ii1 + mi;   ii2 <= ii2 + ii1;   ii3 <= ii3 + ii2;
        qi1 <= qi1 + mq;   qi2 <= qi2 + qi1;   qi3 <= qi3 + qi2;
    end

    reg [10:0] cnt;
    wire       tick = (cnt == decim - 11'd1);
    always @(posedge clk) begin
        if (sync || tick) cnt <= 11'd0;
        else              cnt <= cnt + 11'd1;
    end

    // combs, at the output rate
    reg signed [W-1:0] ic1, ic2, ic3, qc1, qc2, qc3;
    wire signed [W-1:0] id1 = ii3 - ic1, id2 = id1 - ic2, id3 = id2 - ic3;
    wire signed [W-1:0] qd1 = qi3 - qc1, qd2 = qd1 - qc2, qd3 = qd2 - qc3;
    wire signed [W-1:0] is = id3 >>> shift;
    wire signed [W-1:0] qs = qd3 >>> shift;

    always @(posedge clk) begin
        valid <= tick && !sync;
        if (tick) begin
            ic1 <= ii3;  ic2 <= id1;  ic3 <= id2;
            qc1 <= qi3;  qc2 <= qd1;  qc3 <= qd2;
            i <= is[31:0];
            q <= qs[31:0];
        end
    end

    initial begin
        ii1 = 0; ii2 = 0; ii3 = 0; qi1 = 0; qi2 = 0; qi3 = 0;
        ic1 = 0; ic2 = 0; ic3 = 0; qc1 = 0; qc2 = 0; qc3 = 0;
        cnt = 0; valid = 0; i = 0; q = 0; mi = 0; mq = 0;
    end
endmodule
