/*
 * Copyright (c) 2013 Timothy Arceri <t_arceri@yahoo.com.au>
 * Copyright (c) 2018 Mark Janes <mark.a.janes@intel.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * on the rights to use, copy, modify, merge, publish, distribute, sub
 * license, and/or sell copies of the Software, and to permit persons to whom
 * the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice (including the next
 * paragraph) shall be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NON-INFRINGEMENT.  IN NO EVENT SHALL AUTHORS AND/OR THEIR SUPPLIERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include "piglit-util-gl.h"

PIGLIT_GL_TEST_CONFIG_BEGIN

#ifdef PIGLIT_USE_OPENGL
	config.supports_gl_compat_version = 11;
	config.require_debug_context = true;
#else /* using GLES */
	config.supports_gl_es_version = 20;
#endif

	config.window_visual = PIGLIT_GL_VISUAL_RGBA | PIGLIT_GL_VISUAL_DOUBLE;
	config.khr_no_error_support = PIGLIT_NO_ERRORS;

PIGLIT_GL_TEST_CONFIG_END

#ifdef PIGLIT_USE_OPENGL
#define GET_FUNC(x) x
#else /* using GLES */
#define GET_FUNC(x) x ## KHR
#endif

static PFNGLGETDEBUGMESSAGELOGPROC GetDebugMessageLog;
static PFNGLDEBUGMESSAGEINSERTPROC DebugMessageInsert;
static PFNGLDEBUGMESSAGECONTROLPROC DebugMessageControl;

static
sizei fetch_one_long_message(GLint length)
{
  char *buf = (char*) malloc(length);
  sizei msg_size = 0;
  GetDebugMessageLog(1, length, NULL, NULL, NULL, NULL, &msg_size, buf);
  free(buf);
  return msg_size;
}

static void insert_long_message(GLint length)
{
  char *buf = (char*) malloc(length + 1);

  char letter = 'a';
  for (int i = 0; i < length; ++i) {
    buf[i] = letter;
    letter += 1;
    if (letter > 'z')
      letter = 'a';
  }
  buf[length] = '\0';
  DebugMessageInsert(GL_DEBUG_SOURCE_APPLICATION, GL_DEBUG_TYPE_MARKER, 1,
		     GL_DEBUG_SEVERITY_NOTIFICATION, length, buf);
}


/*
 * Test Push/Pop Debug Group
 */
static bool test_large_message()
{
  bool pass = true;
  GLint maxMessageLength;
  GLint maxMessageLogLength;

  glGetIntegerv(GL_MAX_DEBUG_MESSAGE_LENGTH, &maxMessageLength);

  puts("Testing Maximum debug message size");

  /* Setup of the default active debug group, only enabling
   * the messages we will be interested in.
   */
  DebugMessageControl(GL_DONT_CARE, GL_DONT_CARE,
		      GL_DONT_CARE, 0, NULL, GL_FALSE);
  DebugMessageControl(GL_DEBUG_SOURCE_APPLICATION, GL_DEBUG_TYPE_MARKER,
		      GL_DEBUG_SEVERITY_NOTIFICATION, 0, NULL, GL_TRUE);

  /* clear_message_log */
  while(fetch_one_long_message(maxMessageLength))
    /* empty */ ;

  insert_long_message(maxMessageLength);

  size_i msg_len = fetch_one_long_message(maxMessageLength);

  if (msg_len != maxMessageLength) {
    fprintf(stderr, "GL_MAX_DEBUG_MESSAGE_LENGTH is %i but retrieved message of length %i\n",
	    maxMessageLength, msg_len);
    return false;
  }
  return true;
}

void piglit_init(int argc, char **argv)
{
  bool pass = true;

  GetDebugMessageLog = GET_FUNC(glGetDebugMessageLog);
  DebugMessageInsert = GET_FUNC(glDebugMessageInsert);
  DebugMessageControl = GET_FUNC(glDebugMessageControl);

  piglit_require_extension("GL_KHR_debug");

  glEnable(GL_DEBUG_OUTPUT);

  if (!piglit_check_gl_error(GL_NO_ERROR))
    piglit_report_result(PIGLIT_FAIL);

  /* test message control and debug groups */
  return test_large_message();
}

enum piglit_result
piglit_display(void)
{
  return PIGLIT_PASS;
}
