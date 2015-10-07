/* [config]
 * expect_result: pass
 * glsl_version: 1.10
 * [end config]
 */

const float cf = 2.0;
float gf1 = 1.0;
float gf2 = (cf, 3.0);

void main()
{
    gl_Position = vec4(gf1, gf2, cf, 1.0);
}
